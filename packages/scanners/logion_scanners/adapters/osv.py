"""Google OSV-Scanner.

Runs either via Docker (``docker run ghcr.io/google/osv-scanner``)
for local development, or via a native ``osv-scanner`` binary on PATH
when a ``binary_path`` is supplied — for environments that have the
binary installed but no Docker daemon available.
"""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B404
from pathlib import Path
from typing import ClassVar

from logion_scanners.adapters.base import BaseScanner
from logion_scanners.models import (
    SCANNER_OSV,
    ScannerFinding,
    ScannerResult,
)

logger = logging.getLogger(__name__)


def _extract_cvss_base(vector: str) -> float | None:
    """Extract the CVSS base score from a CVSS vector string.

    OSV sometimes provides ``severity[].score`` as a CVSS vector
    like ``"CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"``
    instead of a numeric value.  We cannot compute a score from
    the vector without the full CVSS calculator, so we return
    ``None`` and let the caller fall back to ``"low"``.
    """
    _ = vector  # acknowledged — no calculator available
    return None


class OsvScanner(BaseScanner):
    """Google OSV-Scanner (Docker or native binary)."""

    layer = SCANNER_OSV

    _SEVERITY_MAP: ClassVar[dict[str, str]] = {
        "CRITICAL": "critical",
        "HIGH": "high",
        "MEDIUM": "medium",
        "LOW": "low",
    }

    @staticmethod
    def _cvss_to_severity(score: str | float) -> str:
        """Map a CVSS numeric score to a severity band."""
        try:
            s = float(score)
        except (ValueError, TypeError):
            return "low"
        if s >= 9.0:
            return "critical"
        if s >= 7.0:
            return "high"
        if s >= 4.0:
            return "medium"
        return "low"

    def __init__(
        self,
        *,
        docker_image: str = "ghcr.io/google/osv-scanner:latest",
        binary_path: str | None = None,
        timeout_seconds: int = 300,
    ) -> None:
        # When ``binary_path`` is set, the native binary is invoked
        # directly and Docker is never used.  This is the hosted-worker
        # path; ``docker_image`` is ignored in that mode.
        self._image = docker_image
        self._binary_path = binary_path
        self._timeout = timeout_seconds

    @property
    def _native(self) -> bool:
        return self._binary_path is not None

    def _build_cmd(self, abs_bundle: Path) -> list[str]:
        scan_args = [
            "scan",
            "source",
            "--format",
            "json",
            "--recursive",
        ]
        if self._binary_path is not None:
            # Native binary scans the host path directly — no mount.
            return [self._binary_path, *scan_args, str(abs_bundle)]
        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{abs_bundle}:/scan:ro",
            self._image,
            *scan_args,
            "/scan",
        ]

    def scan(self, bundle_path: Path) -> ScannerResult:
        # Resolve to absolute path — Docker -v requires it, and the
        # native binary benefits from an unambiguous target.
        abs_bundle = bundle_path.resolve()

        cmd = self._build_cmd(abs_bundle)

        try:
            proc = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except FileNotFoundError:
            error = (
                f"OSV-Scanner binary not found at {self._binary_path!r} — "
                "native scan skipped. "
                "Ensure the osv-scanner binary is installed and on PATH."
                if self._native
                else (
                    "Docker is not available — "
                    "OSV scan skipped. "
                    "Install Docker to run OSV-Scanner."
                )
            )
            return ScannerResult(
                layer=SCANNER_OSV,
                passed=False,
                findings=[],
                error=error,
            )
        except subprocess.TimeoutExpired:
            return ScannerResult(
                layer=SCANNER_OSV,
                passed=False,
                findings=[],
                error=f"OSV scan timed out after {self._timeout}s",
            )

        combined = proc.stdout + "\n" + proc.stderr

        # Docker exit 125 covers several failure modes.
        # Only treat as "Docker not available" when the daemon
        # is truly missing; mount/pull failures get a distinct
        # message so the CLI can differentiate.  Docker-specific —
        # the native binary never returns 125, so skip in native mode.
        if not self._native and proc.returncode == 125:
            if "is the docker daemon running" in combined.lower():
                error = (
                    "Docker is not available — "
                    "OSV scan skipped. "
                    "Install Docker or start the Docker daemon."
                )
            else:
                error = (
                    f"OSV Docker container failed to start. "
                    f"Exit 125: {combined[:500]}"
                )
            return ScannerResult(
                layer=SCANNER_OSV,
                passed=False,
                findings=[],
                raw_output=combined,
                error=error,
            )

        # osv-scanner v2 exit codes:
        #   0   — scan ran, no vulns
        #   1   — scan ran, vulns found (JSON is still valid)
        #   128 — no recognizable package manifests in the tree
        #         (e.g. a documentation/skill bundle with no
        #         lockfiles).  Treat as a clean pass.
        if proc.returncode == 128:
            return ScannerResult(
                layer=SCANNER_OSV,
                passed=True,
                findings=[],
                raw_output=combined,
            )
        if proc.returncode not in (0, 1):
            return ScannerResult(
                layer=SCANNER_OSV,
                passed=False,
                findings=[],
                raw_output=combined,
                error=(f"OSV scanner exited with code {proc.returncode}"),
            )

        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError:
            if proc.returncode == 0:
                return ScannerResult(
                    layer=SCANNER_OSV,
                    passed=True,
                    findings=[],
                    raw_output=combined,
                )
            return ScannerResult(
                layer=SCANNER_OSV,
                passed=False,
                findings=[],
                raw_output=combined,
                error="Failed to parse OSV scanner JSON",
            )

        findings = self._parse_findings(report)
        has_critical_or_high = any(
            f.severity in ("critical", "high") for f in findings
        )

        return ScannerResult(
            layer=SCANNER_OSV,
            passed=not has_critical_or_high,
            findings=findings,
            raw_output=combined,
        )

    @staticmethod
    def _resolve_vuln_severity(
        vuln: dict,
        group_severity: dict[str, str],
    ) -> str:
        """Determine the severity for a single vulnerability."""
        vuln_id = vuln.get("id", "")
        cached = group_severity.get(vuln_id)
        if cached is not None:
            return cached

        severity_field = vuln.get("severity")
        if isinstance(severity_field, list):
            scores = OsvScanner._extract_numeric_scores(severity_field)
            if scores:
                return OsvScanner._cvss_to_severity(max(scores))
            return "low"
        if isinstance(severity_field, str):
            return OsvScanner._SEVERITY_MAP.get(severity_field.upper(), "low")
        return "low"

    @staticmethod
    def _extract_numeric_scores(
        severity_list: list[dict],
    ) -> list[float]:
        """Extract numeric CVSS scores from a severity array."""
        numeric_scores: list[float] = []
        for s in severity_list:
            if not isinstance(s, dict):
                continue
            raw_score = s.get("score")
            if raw_score is None:
                continue
            try:
                numeric_scores.append(float(raw_score))
            except (ValueError, TypeError):
                cvss_base = _extract_cvss_base(str(raw_score))
                if cvss_base is not None:
                    numeric_scores.append(cvss_base)
        return numeric_scores

    @staticmethod
    def _parse_findings(
        report: dict,
    ) -> list[ScannerFinding]:
        findings: list[ScannerFinding] = []
        for result in report.get("results", []):
            source = result.get("source", {})
            source_path = source.get("path", "")
            for pkg in result.get("packages", []):
                group_severity: dict[str, str] = {}
                for group in pkg.get("groups", []):
                    severity_raw = group.get("max_severity")
                    if severity_raw is not None:
                        sev = OsvScanner._cvss_to_severity(severity_raw)
                        for vid in group.get("ids", []):
                            group_severity[vid] = sev

                pkg_name = pkg.get("package", {}).get("name", "")
                for vuln in pkg.get("vulnerabilities", []):
                    vuln_id = vuln.get("id", "UNKNOWN")
                    summary = vuln.get("summary", "")[:200]
                    vuln_sev = OsvScanner._resolve_vuln_severity(
                        vuln, group_severity
                    )

                    findings.append(
                        ScannerFinding(
                            layer=SCANNER_OSV,
                            severity=vuln_sev,
                            rule_id=f"OSV-{vuln_id}",
                            description=(
                                f"{vuln_id} in {pkg_name}: {summary}"
                                if pkg_name
                                else f"{vuln_id}: {summary}"
                            ),
                            file_path=source_path or None,
                            raw_output=json.dumps(vuln)[:4096],
                        )
                    )
        return findings

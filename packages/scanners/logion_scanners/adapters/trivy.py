"""Trivy filesystem scanner.

Runs either via Docker (``docker run aquasec/trivy``) for local
development, or via a native ``trivy`` binary on PATH when a
``binary_path`` is supplied — for environments that have the binary
installed but no Docker daemon available.
"""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B404
from pathlib import Path

from logion_scanners.adapters.base import BaseScanner
from logion_scanners.models import (
    SCANNER_TRIVY,
    ScannerFinding,
    ScannerResult,
)

logger = logging.getLogger(__name__)
_OUTPUT_SNIPPET_LIMIT = 500

_SEVERITY_MAP: dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "UNKNOWN": "low",
}

_DOCKER_UNAVAILABLE_MSG = (
    "Docker is not available — "
    "{scanner} scan skipped. "
    "Install Docker or start the Docker daemon."
)

_BINARY_NOT_FOUND_MSG = (
    "Trivy binary not found at {binary!r} — "
    "native scan skipped. "
    "Ensure the trivy binary is installed and on PATH."
)


class TrivyScanner(BaseScanner):
    """Trivy filesystem scanner (Docker or native binary)."""

    layer = SCANNER_TRIVY

    def __init__(
        self,
        *,
        docker_image: str = "aquasec/trivy:latest",
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
            "fs",
            "--format",
            "json",
            "--severity",
            "CRITICAL,HIGH,MEDIUM,LOW",
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
                _BINARY_NOT_FOUND_MSG.format(binary=self._binary_path)
                if self._native
                else _DOCKER_UNAVAILABLE_MSG.format(scanner="Trivy")
            )
            return ScannerResult(
                layer=SCANNER_TRIVY,
                passed=False,
                findings=[],
                error=error,
            )
        except subprocess.TimeoutExpired as exc:
            raw = exc.stdout if isinstance(exc.stdout, str) else None
            return ScannerResult(
                layer=SCANNER_TRIVY,
                passed=False,
                findings=[],
                raw_output=raw,
                error=f"Trivy scan timed out after {self._timeout}s",
            )

        combined = proc.stdout + "\n" + proc.stderr

        # Docker exit 125 covers several failure modes.  We only
        # treat it as "Docker not available" when the daemon is
        # truly missing; mount / pull failures get a distinct message
        # so the CLI can differentiate (exit 2 vs scan error).  This
        # is Docker-specific — the native binary never returns 125 for
        # these reasons, so skip it in native mode.
        if not self._native and proc.returncode == 125:
            if "Is the docker daemon running" in combined.lower():
                error = _DOCKER_UNAVAILABLE_MSG.format(scanner="Trivy")
            else:
                error = (
                    f"Trivy Docker container failed to start. "
                    f"Exit 125: {combined[:500]}"
                )
            return ScannerResult(
                layer=SCANNER_TRIVY,
                passed=False,
                findings=[],
                raw_output=combined,
                error=error,
            )

        if proc.returncode not in (0, 1):
            return ScannerResult(
                layer=SCANNER_TRIVY,
                passed=False,
                findings=[],
                raw_output=combined,
                error=f"Trivy exited with code {proc.returncode}",
            )

        try:
            report = self._load_json_report(proc.stdout)
        except json.JSONDecodeError:
            return ScannerResult(
                layer=SCANNER_TRIVY,
                passed=False,
                findings=[],
                raw_output=combined,
                error=(
                    "Failed to parse Trivy JSON output. "
                    f"stdout={self._snippet(proc.stdout)!r}; "
                    f"stderr={self._snippet(proc.stderr)!r}"
                ),
            )

        findings = self._parse_findings(report)
        has_critical_or_high = any(
            f.severity in ("critical", "high") for f in findings
        )

        return ScannerResult(
            layer=SCANNER_TRIVY,
            passed=not has_critical_or_high,
            findings=findings,
            raw_output=combined,
        )

    @staticmethod
    def _load_json_report(output: str) -> dict:
        """Load Trivy JSON even when progress text wraps stdout."""
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            for index, char in enumerate(output):
                if char != "{":
                    continue
                try:
                    value, _ = decoder.raw_decode(output[index:])
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    return value
            raise

    @staticmethod
    def _snippet(output: str) -> str:
        """Return a compact diagnostic snippet without huge scanner output."""
        normalized = " ".join(output.split())
        if len(normalized) <= _OUTPUT_SNIPPET_LIMIT:
            return normalized
        return normalized[:_OUTPUT_SNIPPET_LIMIT] + "..."

    @staticmethod
    def _parse_findings(
        report: dict,
    ) -> list[ScannerFinding]:
        findings: list[ScannerFinding] = []
        for result in report.get("Results", []):
            target = result.get("Target", "")
            for vuln in result.get("Vulnerabilities", []):
                sev = _SEVERITY_MAP.get(
                    vuln.get("Severity", "").upper(), "low"
                )
                vuln_id = vuln.get("VulnerabilityID", "UNKNOWN")
                title = vuln.get("Title") or vuln.get("Description", "")[:200]
                pkg_name = vuln.get("PkgName", "")
                findings.append(
                    ScannerFinding(
                        layer=SCANNER_TRIVY,
                        severity=sev,
                        rule_id=f"TRIVY-{vuln_id}",
                        description=(
                            f"{vuln_id} in {pkg_name}: {title}"
                            if pkg_name
                            else f"{vuln_id}: {title}"
                        ),
                        file_path=target or None,
                        raw_output=json.dumps(vuln)[:4096],
                    )
                )
        return findings

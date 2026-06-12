"""Google OSV-Scanner running inside Docker."""

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


class OsvScanner(BaseScanner):
    """Google OSV-Scanner running inside Docker."""

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
        timeout_seconds: int = 300,
    ) -> None:
        self._image = docker_image
        self._timeout = timeout_seconds

    def scan(self, bundle_path: Path) -> ScannerResult:
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{bundle_path}:/scan:ro",
            self._image,
            "scan",
            "source",
            "--format",
            "json",
            "--recursive",
            "/scan",
        ]

        try:
            proc = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except FileNotFoundError:
            return ScannerResult(
                layer=SCANNER_OSV,
                passed=False,
                findings=[],
                error=(
                    "Docker is not available — "
                    "OSV scan skipped. "
                    "Install Docker to run OSV-Scanner."
                ),
            )
        except subprocess.TimeoutExpired:
            return ScannerResult(
                layer=SCANNER_OSV,
                passed=False,
                findings=[],
                error=f"OSV scan timed out after {self._timeout}s",
            )

        combined = proc.stdout + "\n" + proc.stderr

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

                    vuln_sev: str | None = group_severity.get(vuln_id)
                    if vuln_sev is None:
                        severity_field = vuln.get("severity")
                        if isinstance(severity_field, list):
                            numeric_scores = [
                                float(s["score"])
                                for s in severity_field
                                if isinstance(s, dict) and "score" in s
                            ]
                            if numeric_scores:
                                vuln_sev = OsvScanner._cvss_to_severity(
                                    max(numeric_scores)
                                )
                            else:
                                vuln_sev = "low"
                        elif isinstance(severity_field, str):
                            vuln_sev = OsvScanner._SEVERITY_MAP.get(
                                severity_field.upper(), "low"
                            )
                        else:
                            vuln_sev = "low"

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

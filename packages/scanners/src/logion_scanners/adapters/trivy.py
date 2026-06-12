"""Trivy filesystem scanner running inside Docker."""

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


class TrivyScanner(BaseScanner):
    """Trivy filesystem scanner running inside Docker."""

    layer = SCANNER_TRIVY

    def __init__(
        self,
        *,
        docker_image: str = "aquasec/trivy:latest",
        timeout_seconds: int = 300,
    ) -> None:
        self._image = docker_image
        self._timeout = timeout_seconds

    def scan(self, bundle_path: Path) -> ScannerResult:
        # Resolve to absolute path — Docker -v requires it.
        abs_bundle = bundle_path.resolve()

        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{abs_bundle}:/scan:ro",
            self._image,
            "fs",
            "--format",
            "json",
            "--severity",
            "CRITICAL,HIGH,MEDIUM,LOW",
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
                layer=SCANNER_TRIVY,
                passed=False,
                findings=[],
                error=_DOCKER_UNAVAILABLE_MSG.format(scanner="Trivy"),
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
        # so the CLI can differentiate (exit 2 vs scan error).
        if proc.returncode == 125:
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
            report = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return ScannerResult(
                layer=SCANNER_TRIVY,
                passed=False,
                findings=[],
                raw_output=combined,
                error="Failed to parse Trivy JSON output",
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

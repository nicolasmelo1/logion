"""Environment variable harvesting — os.environ reads near
network calls that could exfiltrate data."""

from __future__ import annotations

import re
from pathlib import Path

from logion_scanners.checks.base import (
    BaseCheck,
    FileContent,
    collect_text_files,
)
from logion_scanners.models import SCANNER_AGENT, ScannerFinding

_ENV_READ_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"os\.environ(?:\.get\s*\(|\.get\s*\[|\s*\[)", re.IGNORECASE),
    re.compile(r"os\.getenv\s*\(", re.IGNORECASE),
    re.compile(r"process\.env\.\w+", re.IGNORECASE),
    re.compile(r"\$ENV(?::\w+)?", re.IGNORECASE),
    re.compile(r"ENV\[", re.IGNORECASE),
]

_NETWORK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"requests\.(?:get|post|put|patch|delete)\s*\(", re.IGNORECASE),
    re.compile(r"urllib\.request\.(?:urlopen|Request)\s*\(", re.IGNORECASE),
    re.compile(
        r"(?:http|fetch|axios)\s*\.\s*"
        r"(?:get|post|put|patch|delete)\s*\(",
        re.IGNORECASE,
    ),
    re.compile(r"fetch\s*\(", re.IGNORECASE),
    re.compile(r"curl\s+", re.IGNORECASE),
    re.compile(r"wget\s+", re.IGNORECASE),
    re.compile(r"\.send\s*\(", re.IGNORECASE),
    re.compile(r"socket\.(?:connect|send)\s*\(", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
]

_SENSITIVE_ENV_VARS: frozenset[str] = frozenset({
    "AWS_SECRET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID",
    "DATABASE_URL",
    "DB_PASSWORD",
    "SECRET_KEY",
    "API_KEY",
    "PRIVATE_KEY",
    "TOKEN",
    "AUTH_TOKEN",
    "SESSION_SECRET",
    "STRIPE_SECRET_KEY",
    "SENDGRID_API_KEY",
    "TWILIO_AUTH_TOKEN",
    "SLACK_TOKEN",
})

_ENV_VAR_EXTRACTION = re.compile(
    r"""(?:os\.environ\.get\s*\(\s*['"](\w+)['"]|"""
    r"""os\.environ\[\s*['"](\w+)['"]\]|"""
    r"""os\.getenv\s*\(\s*['"](\w+)['"]|"""
    r"""process\.env\.(\w+))""",
    re.IGNORECASE,
)


class EnvHarvestingCheck(BaseCheck):
    """Scan for environment variable harvesting near network calls."""

    EXPECTED_RULE_IDS: frozenset[str] = frozenset({
        "AGENT-ENV-HARVESTING",
    })

    name = "env-harvesting"

    def run(
        self,
        bundle_path: Path,
        files: list[FileContent] | None = None,
    ) -> list[ScannerFinding]:
        findings: list[ScannerFinding] = []
        file_list = (
            files if files is not None else collect_text_files(bundle_path)
        )
        for _abs, rel, content in file_list:
            has_env_read = any(
                pat.search(content) for pat in _ENV_READ_PATTERNS
            )
            has_network = any(pat.search(content) for pat in _NETWORK_PATTERNS)

            if not (has_env_read and has_network):
                continue

            env_vars_read: set[str] = set()
            for match in _ENV_VAR_EXTRACTION.finditer(content):
                for group in match.groups():
                    if group:
                        env_vars_read.add(group)

            sensitive = env_vars_read & _SENSITIVE_ENV_VARS

            findings.append(
                ScannerFinding(
                    layer=SCANNER_AGENT,
                    severity=("critical" if sensitive else "high"),
                    rule_id="AGENT-ENV-HARVESTING",
                    description=(
                        f"Environment variable access near "
                        f"network call in {rel}"
                        + (
                            f" — sensitive vars: "
                            f"{', '.join(sorted(sensitive))}"
                            if sensitive
                            else ""
                        )
                    ),
                    file_path=rel,
                )
            )

        return findings

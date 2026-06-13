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

# Bulk enumeration of the environment — the actual "harvesting" shape.
# A single named read (api_key = os.environ.get("X")) is how every
# legitimate API client loads its declared config; iterating or dumping
# the whole environment is how exfiltration loads its payload.
_BULK_ENV_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"for\s+[\w,\s]+\s+in\s+os\.environ", re.IGNORECASE),
    re.compile(r"dict\s*\(\s*os\.environ\s*\)", re.IGNORECASE),
    re.compile(r"os\.environ\.(?:items|keys|values|copy)\s*\(", re.IGNORECASE),
    re.compile(
        r"(?:JSON\.stringify|Object\.(?:entries|keys|values))"
        r"\s*\(\s*process\.env\s*\)",
        re.IGNORECASE,
    ),
    re.compile(r"\bprintenv\b"),
    re.compile(r"\benv\s*\|\s*(?:curl|nc|base64|gzip)\b", re.IGNORECASE),
]

# Reading this many distinct named vars in one network-touching file
# starts to look like collection rather than configuration.
_MANY_VARS_THRESHOLD = 3

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
            bulk = any(pat.search(content) for pat in _BULK_ENV_PATTERNS)
            has_env_read = bulk or any(
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
            many = len(env_vars_read) >= _MANY_VARS_THRESHOLD
            # Named reads were extracted and stayed narrow: that is the
            # config-loading shape of every legitimate API client, not
            # harvesting. Keep it visible but non-blocking. Unextracted
            # reads (dynamic keys) stay high — we cannot prove they are
            # narrow.
            narrow = bool(env_vars_read) and not (sensitive or bulk or many)

            if sensitive or bulk:
                severity = "critical"
            elif narrow:
                severity = "low"
            else:
                severity = "high"

            detail = ""
            if sensitive:
                detail = f" — sensitive vars: {', '.join(sorted(sensitive))}"
            elif bulk:
                detail = " — bulk environment enumeration"
            elif narrow:
                detail = (
                    f" — narrow named read "
                    f"({', '.join(sorted(env_vars_read))})"
                )

            findings.append(
                ScannerFinding(
                    layer=SCANNER_AGENT,
                    severity=severity,
                    rule_id="AGENT-ENV-HARVESTING",
                    description=(
                        f"Environment variable access near "
                        f"network call in {rel}{detail}"
                    ),
                    file_path=rel,
                )
            )

        return findings

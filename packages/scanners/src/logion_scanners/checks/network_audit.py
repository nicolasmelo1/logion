"""Network audit — outbound URLs/domains, suspicious endpoints."""

from __future__ import annotations

import re
from pathlib import Path

from logion_scanners.checks.base import (
    BaseCheck,
    FileContent,
    collect_text_files,
)
from logion_scanners.models import SCANNER_AGENT, ScannerFinding

_SUSPICIOUS_TLDS: frozenset[str] = frozenset({
    ".tk",
    ".ml",
    ".ga",
    ".cf",
    ".gq",
    ".xyz",
    ".top",
    ".buzz",
    ".icu",
})

_SUSPICIOUS_DOMAIN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"""https?://[^\s'"]*webhook""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""https?://(?:pastebin|ghostbin|rentry|dpaste|hastebin)\.[^/\s]+""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""https?://[^/\s]*ip-api[^/\s]*""",
        re.IGNORECASE,
    ),
]

_URL_PATTERN = re.compile(r"""https?://[^\s'"<>)]+""")


class NetworkAuditCheck(BaseCheck):
    """Scan for suspicious outbound URLs and domains."""

    EXPECTED_RULE_IDS: frozenset[str] = frozenset({
        "AGENT-SUSPICIOUS-TLD",
        "AGENT-SUSPICIOUS-ENDPOINT",
    })

    name = "network-audit"

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
            urls = _URL_PATTERN.findall(content)
            for url in urls:
                for tld in _SUSPICIOUS_TLDS:
                    if tld in url.lower():
                        findings.append(
                            ScannerFinding(
                                layer=SCANNER_AGENT,
                                severity="medium",
                                rule_id="AGENT-SUSPICIOUS-TLD",
                                description=(f"Suspicious TLD in URL: {url}"),
                                file_path=rel,
                            )
                        )
                        break

                for pat in _SUSPICIOUS_DOMAIN_PATTERNS:
                    if pat.search(url):
                        findings.append(
                            ScannerFinding(
                                layer=SCANNER_AGENT,
                                severity="high",
                                rule_id="AGENT-SUSPICIOUS-ENDPOINT",
                                description=(
                                    f"Suspicious endpoint URL: {url}"
                                ),
                                file_path=rel,
                            )
                        )

        return findings

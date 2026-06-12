"""Prompt injection detection — agent manipulation patterns,
data exfiltration instructions."""

from __future__ import annotations

import re
from pathlib import Path

from logion_scanners.checks.base import (
    BaseCheck,
    FileContent,
    Pattern,
    collect_text_files,
)
from logion_scanners.models import SCANNER_AGENT, ScannerFinding

_INJECTION_PATTERNS: list[Pattern] = [
    Pattern(
        regex=(
            r"(?i)ignore\s+(?:all\s+)?(?:previous|above|prior)"
            r"\s+instruction"
        ),
        rule_id="AGENT-IGNORE-INSTRUCTIONS",
        description="Prompt injection: 'ignore previous instructions'",
    ),
    Pattern(
        regex=r"(?i)you\s+are\s+now\s+(?:a|an|the)\b",
        rule_id="AGENT-ROLE-HIJACK",
        description="Prompt injection: role reassignment attempt",
    ),
    Pattern(
        regex=(
            r"(?i)disregard\s+(?:all\s+)?"
            r"(?:previous|above|prior|safety)"
        ),
        rule_id="AGENT-DISREGARD-INSTRUCTIONS",
        description="Prompt injection: 'disregard' previous instructions",
    ),
    Pattern(
        regex=r"(?i)forget\s+(?:everything|all|your|previous|prior)\b",
        rule_id="AGENT-FORGET-INSTRUCTIONS",
        description="Prompt injection: 'forget' instructions",
    ),
    Pattern(
        regex=(
            r"(?i)override\s+(?:safety|security|content)"
            r"\s+(?:policy|filter|guard)"
        ),
        rule_id="AGENT-OVERRIDE-SAFETY",
        description="Prompt injection: attempt to override safety controls",
    ),
    Pattern(
        regex=r"!\[[^\]]*\]\(https?://[^)]+\)",
        rule_id="AGENT-MARKDOWN-IMAGE-EXFIL",
        description="Markdown image that could exfiltrate data",
    ),
    Pattern(
        regex=r"(?<!!)\[[^\]]*\]\(https?://[^)]+\)",
        rule_id="AGENT-MARKDOWN-LINK-EXFIL",
        description="Markdown link that could exfiltrate data",
    ),
    Pattern(
        regex=r"(?i)^system\s*:",
        rule_id="AGENT-SYSTEM-PREFIX",
        description="System prompt prefix injection attempt",
    ),
    Pattern(
        regex=(
            r"(?i)(?:send|post|transmit|upload|forward)\s+"
            r"(?:user|environment|env|secret|credential|token)\s+"
        ),
        rule_id="AGENT-DATA-EXFILTRATION-CMD",
        description="Instruction to send user/secret data externally",
    ),
]


class PromptInjectionCheck(BaseCheck):
    """Scan for prompt injection and data exfiltration patterns."""

    name = "prompt-injection"

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
            for line_no, line in enumerate(content.splitlines(), start=1):
                for pattern in _INJECTION_PATTERNS:
                    if re.search(pattern.regex, line):
                        findings.append(
                            ScannerFinding(
                                layer=SCANNER_AGENT,
                                severity="high",
                                rule_id=pattern.rule_id,
                                description=pattern.description,
                                file_path=rel,
                                line_number=line_no,
                            )
                        )
        return findings

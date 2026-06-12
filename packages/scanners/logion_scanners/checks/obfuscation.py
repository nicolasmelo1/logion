"""Obfuscation detection — base64 encoded strings, eval chains,
string manipulation hiding malicious intent."""

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

_OBFUSCATION_PATTERNS: list[Pattern] = [
    Pattern(
        regex=r"[A-Za-z0-9+/]{80,}={0,2}",
        rule_id="AGENT-BASE64-PAYLOAD",
        description="Long base64-encoded string — possible hidden payload",
    ),
    Pattern(
        regex=r"\b(?:eval|exec)\s*\(",
        rule_id="AGENT-EVAL-EXEC",
        description="Use of eval/exec — potential code injection",
    ),
    Pattern(
        regex=r"__import__\s*\(",
        rule_id="AGENT-DYNAMIC-IMPORT",
        description="Dynamic import via __import__ — obfuscation risk",
    ),
    Pattern(
        regex=r"(?:\\x[0-9a-fA-F]{2}){4,}",
        rule_id="AGENT-HEX-ESCAPE-CHAIN",
        description="Long chain of hex escapes — possible obfuscation",
    ),
    Pattern(
        regex=r"getattr\s*\(.+\+.+",
        rule_id="AGENT-GETATTR-CONCAT",
        description="getattr with string concatenation — obfuscation",
    ),
    Pattern(
        regex=r"compile\s*\(.*\).*exec\s*\(",
        rule_id="AGENT-COMPILE-EXEC",
        description="compile+exec pattern — dynamic code execution",
    ),
    Pattern(
        regex=r"chr\s*\(\s*\d+\s*\)[\s+)]{3,}",
        rule_id="AGENT-CHR-CHAIN",
        description="chr() chain building string — obfuscation",
    ),
]


class ObfuscationCheck(BaseCheck):
    """Scan for obfuscation patterns in course bundles."""

    EXPECTED_RULE_IDS: frozenset[str] = frozenset({
        "AGENT-BASE64-PAYLOAD",
        "AGENT-EVAL-EXEC",
        "AGENT-DYNAMIC-IMPORT",
        "AGENT-HEX-ESCAPE-CHAIN",
        "AGENT-GETATTR-CONCAT",
        "AGENT-COMPILE-EXEC",
        "AGENT-CHR-CHAIN",
    })

    name = "obfuscation"

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
            for pattern in _OBFUSCATION_PATTERNS:
                if pattern.rule_id in {
                    "AGENT-BASE64-PAYLOAD",
                    "AGENT-EVAL-EXEC",
                }:
                    for line_no, line in enumerate(
                        content.splitlines(), start=1
                    ):
                        if re.search(pattern.regex, line):
                            findings.append(
                                ScannerFinding(
                                    layer=SCANNER_AGENT,
                                    severity=(
                                        "high"
                                        if pattern.rule_id == "AGENT-EVAL-EXEC"
                                        else "medium"
                                    ),
                                    rule_id=pattern.rule_id,
                                    description=pattern.description,
                                    file_path=rel,
                                    line_number=line_no,
                                )
                            )
                else:
                    if re.search(pattern.regex, content):
                        findings.append(
                            ScannerFinding(
                                layer=SCANNER_AGENT,
                                severity="medium",
                                rule_id=pattern.rule_id,
                                description=pattern.description,
                                file_path=rel,
                            )
                        )
        return findings

"""Secrets detection — API keys, private keys, tokens,
connection strings."""

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

_SECRET_PATTERNS: list[Pattern] = [
    Pattern(
        regex=r"(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}",
        rule_id="AGENT-AWS-ACCESS-KEY",
        description="AWS Access Key ID detected",
    ),
    Pattern(
        regex=(
            r"(?i)(?:api[_-]?key|apikey|api[_-]?secret)"
            r"""\s*[=:]\s*["']?[0-9a-zA-Z]{20,}["']?"""
        ),
        rule_id="AGENT-HARDCODED-API-KEY",
        description="Hardcoded API key detected",
    ),
    Pattern(
        regex=r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        rule_id="AGENT-PRIVATE-KEY-EXPOSED",
        description="Private key embedded in course file",
    ),
    Pattern(
        regex=r"(?:ghp|gho|ghu|ghs|ghr)_[0-9a-zA-Z]{36,}",
        rule_id="AGENT-GITHUB-TOKEN",
        description="GitHub personal/access token detected",
    ),
    Pattern(
        regex=(
            r"""(?i)(?:postgres|mysql|mongodb|redis)://"""
            r"""[^\s"']+:"""
            r"""[^\s"']+@[^\s"']+"""
        ),
        rule_id="AGENT-DB-CONNECTION-STRING",
        description="Database connection string with credentials",
    ),
    Pattern(
        regex=r"xox[baprs]-[0-9a-zA-Z-]{10,}",
        rule_id="AGENT-SLACK-TOKEN",
        description="Slack token detected",
    ),
    Pattern(
        regex=r"(?:sk|pk)_(?:test|live)_[0-9a-zA-Z]{24,}",
        rule_id="AGENT-STRIPE-KEY",
        description="Stripe API key detected",
    ),
    Pattern(
        regex=(
            r"""(?i)(?:secret|token|password|passwd)"""
            r"""\s*[=:]\s*["']"""
            r"""[0-9a-zA-Z!@#$%^&*]{16,}"""
            r"""["']"""
        ),
        rule_id="AGENT-HARDCODED-SECRET",
        description="Hardcoded secret/token/password detected",
    ),
]


class SecretsDetectionCheck(BaseCheck):
    """Scan for hardcoded secrets and credentials."""

    name = "secrets-detection"

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
                for pattern in _SECRET_PATTERNS:
                    if re.search(pattern.regex, line):
                        findings.append(
                            ScannerFinding(
                                layer=SCANNER_AGENT,
                                severity="critical",
                                rule_id=pattern.rule_id,
                                description=pattern.description,
                                file_path=rel,
                                line_number=line_no,
                            )
                        )
        return findings

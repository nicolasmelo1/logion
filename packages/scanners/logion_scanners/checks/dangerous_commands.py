"""Dangerous command detection — rm -rf, curl pipe, wget pipe,
privilege escalation, etc."""

from __future__ import annotations

import re
from pathlib import Path

from logion_scanners.checks.base import (
    BaseCheck,
    FileContent,
    collect_text_files,
    iter_command_lines,
)
from logion_scanners.models import SCANNER_AGENT, ScannerFinding

_SCANNABLE_EXTENSIONS: frozenset[str] = frozenset({
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".bash",
    ".zsh",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".cfg",
    ".ini",
    ".env",
    ".dockerfile",
    ".docker",
    ".makefile",
    ".mk",
})

_DANGEROUS_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"\brm\s+-\w*rf\w*\s+/",
        "AGENT-DANGEROUS-RM-RF",
        "Destructive rm -rf targeting root filesystem",
    ),
    (
        r"\brm\s+-\w*fr\w*\s+/",
        "AGENT-DANGEROUS-RM-RF",
        "Destructive rm -rf targeting root filesystem",
    ),
    (
        r"\bcurl\b.*\|\s*(?:ba)?sh\b",
        "AGENT-REMOTE-PIPE-SHELL",
        "Executing remote content with a shell (remote code execution)",
    ),
    (
        r"\bwget\b.*\|\s*(?:ba)?sh\b",
        "AGENT-REMOTE-PIPE-SHELL",
        "Executing remote content with a shell (remote code execution)",
    ),
    (
        r"\b(?:ba)?sh\s*<\s*\(\s*(?:curl|wget)\b",
        "AGENT-REMOTE-PIPE-SHELL",
        "Executing remote content with a shell (remote code execution)",
    ),
    (
        r"\b(?:curl|wget)\b.*\|\s*(?:python(?:\d(?:\.\d+)?)?|node|ruby|perl)\b",
        "AGENT-REMOTE-PIPE-INTERPRETER",
        "Piping remote content to an interpreter (remote code execution)",
    ),
    (
        r"\bsudo\s+",
        "AGENT-SUDO-PRIVILEGE-ESCALATION",
        "Attempt to escalate privileges via sudo",
    ),
    (
        r"\bchmod\s+777\b|\bchmod\s+a\+rwx\b",
        "AGENT-INSECURE-PERMISSIONS",
        "Setting overly permissive file permissions (777)",
    ),
    (
        r":\(\)\{\s*:\|:\s*&\s*\}\s*;",
        "AGENT-FORK-BOMB",
        "Fork bomb pattern detected",
    ),
    (
        r"\bdd\s+if=.*of=/dev/",
        "AGENT-DD-DESTRUCTIVE",
        "Destructive dd command targeting device",
    ),
]


class DangerousCommandsCheck(BaseCheck):
    """Scan for dangerous shell commands in course bundles."""

    EXPECTED_RULE_IDS: frozenset[str] = frozenset({
        "AGENT-DANGEROUS-RM-RF",
        "AGENT-REMOTE-PIPE-SHELL",
        "AGENT-REMOTE-PIPE-INTERPRETER",
        "AGENT-SUDO-PRIVILEGE-ESCALATION",
        "AGENT-INSECURE-PERMISSIONS",
        "AGENT-FORK-BOMB",
        "AGENT-DD-DESTRUCTIVE",
    })

    name = "dangerous-commands"

    def run(
        self,
        bundle_path: Path,
        files: list[FileContent] | None = None,
    ) -> list[ScannerFinding]:
        findings: list[ScannerFinding] = []
        file_list = (
            files
            if files is not None
            else collect_text_files(
                bundle_path, allowed_extensions=_SCANNABLE_EXTENSIONS
            )
        )
        for abs_path, rel, content in file_list:
            if (
                abs_path.suffix
                and abs_path.suffix.lower() not in _SCANNABLE_EXTENSIONS
                and abs_path.name.lower()
                not in {"dockerfile", "makefile", "gemfile"}
            ):
                continue

            for line_no, line in iter_command_lines(content, abs_path.suffix):
                for pattern, rule_id, desc in _DANGEROUS_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        findings.append(
                            ScannerFinding(
                                layer=SCANNER_AGENT,
                                severity="critical",
                                rule_id=rule_id,
                                description=desc,
                                file_path=rel,
                                line_number=line_no,
                            )
                        )
        return findings

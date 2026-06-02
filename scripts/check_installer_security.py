#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Security guardrails for curl-able installer sources.

The installer is a high-trust entrypoint: users may run it before they have
any other Logion code. This check intentionally scans only production
installer sources and blocks patterns that are too dangerous to accept without
an explicit, reviewed exception.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

INSTALLER_FILES = (
    "scripts/install.sh",
    "scripts/install_lib.sh",
    "scripts/install.ps1",
    "scripts/install_lib.ps1",
)


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    message: str


RULES: tuple[Rule, ...] = (
    Rule(
        "dynamic shell evaluation",
        re.compile(r"\b(eval|Invoke-Expression|iex)\b", re.IGNORECASE),
        "Do not dynamically execute strings in installers.",
    ),
    Rule(
        "unreviewed curl pipe shell",
        re.compile(r"\b(curl|wget)\b[^\n|;&]*\|\s*(sh|bash|zsh|pwsh|powershell)\b"),
        "Pipe-to-shell is only allowed for explicitly allowlisted domains.",
    ),
    Rule(
        "non-TLS download",
        re.compile(r"\bhttps?://[^\s\"']+", re.IGNORECASE),
        "Installer downloads must use allowlisted HTTPS origins.",
    ),
    Rule(
        "unsafe recursive delete",
        re.compile(r"\brm\s+-[A-Za-z]*r[A-Za-z]*f?[A-Za-z]*\s+(/|\$HOME|~)(\s|$)"),
        "Never recursively delete root or the user's home directory.",
    ),
    Rule(
        "world-writable permissions",
        re.compile(r"\bchmod\s+(777|a\+w)\b", re.IGNORECASE),
        "Do not create world-writable installer paths.",
    ),
    Rule(
        "privilege escalation",
        re.compile(r"\b(sudo|su\s+-|Start-Process\s+.*-Verb\s+RunAs)\b", re.IGNORECASE),
        "Installers must not escalate privileges automatically.",
    ),
    Rule(
        "startup persistence",
        re.compile(
            r"(crontab|LaunchAgents|LaunchDaemons|systemd|\.service\b|"
            r"CurrentVersion\\Run)",
            re.IGNORECASE,
        ),
        "Installer must not add background startup persistence.",
    ),
    Rule(
        "profile command injection",
        re.compile(r">>\s*(\$HOME|~)/\.(bashrc|zshrc|profile|config/fish/config\.fish)"),
        "Profile writes must go through the reviewed update_path helper.",
    ),
    Rule(
        "prompt injection language",
        re.compile(
            r"(ignore (all )?(previous|prior) instructions|developer message|"
            r"system prompt|prompt injection)",
            re.IGNORECASE,
        ),
        "Installer files must not contain prompt-injection instructions.",
    ),
)

ALLOWED_DOWNLOAD_ORIGINS = (
    "https://logion.dev/",
    "https://docs.logion.sh",
    "https://github.com/nicolasmelo1/logion/",
    "https://astral.sh/uv/",
)

ALLOWED_PIPE_TO_SHELL = (
    "curl -fsSL https://astral.sh/uv/install.sh | sh",
    "curl -LsSf https://astral.sh/uv/install.sh | sh",
)

ALLOWED_PROFILE_WRITES = (
    'printf \'%s\\n\' "$_line" >> "$_rc"',
    'printf \'%s\\n\' "$_fish_line" >> "$_fish_rc"',
)


def is_allowed(rule_name: str, line: str) -> bool:
    stripped = line.strip()
    if rule_name == "unreviewed curl pipe shell":
        return any(command in stripped for command in ALLOWED_PIPE_TO_SHELL)
    if rule_name == "non-TLS download":
        urls = re.findall(r"\bhttps?://[^\s\"']+", line, re.IGNORECASE)
        return all(
            url.startswith(ALLOWED_DOWNLOAD_ORIGINS) and url.startswith("https://")
            for url in urls
        )
    if rule_name == "profile command injection":
        return stripped in ALLOWED_PROFILE_WRITES
    if rule_name == "privilege escalation":
        return '_hint="Try: sudo ' in stripped
    return False


def scan_file(rel_path: str) -> list[tuple[str, int, str, str]]:
    path = os.path.join(ROOT, rel_path)
    hits: list[tuple[str, int, str, str]] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if line.lstrip().startswith("#"):
                continue
            for rule in RULES:
                if rule.pattern.search(line) and not is_allowed(rule.name, line):
                    hits.append((rel_path, lineno, rule.name, rule.message))
    return hits


def main() -> None:
    hits: list[tuple[str, int, str, str]] = []
    for rel_path in INSTALLER_FILES:
        hits.extend(scan_file(rel_path))

    if not hits:
        print("check_installer_security: ok.")
        return

    print("check_installer_security: unsafe installer patterns detected:")
    for rel_path, lineno, rule_name, message in hits:
        print(f"  {rel_path}:{lineno}  [{rule_name}] {message}")
    print(
        "\nIf a pattern is truly required, make it narrow and add an explicit "
        "allowlist entry in scripts/check_installer_security.py with a comment."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()

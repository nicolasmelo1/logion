"""Runtime install attempt detection — package-manager install
commands that extend the environment at runtime.

These are not *dangerous* commands in the destructive sense (users run
`npm install` daily); they are **trust-surface-expanding** commands that
contradict the bundle's declared capability manifest. A course bundle
must be self-contained: it may assume an environment, but it may not
extend it. Anything installed at runtime is invisible to the capability
scanner, unpinned, and mutable after publication review approved the
bundle (the ClawHub supply-chain pattern).

`curl | sh` / `wget | sh` are intentionally NOT covered here — they are
already flagged by dangerous_commands.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from logion_scanners.checks.base import (
    BaseCheck,
    FileContent,
    collect_text_files,
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

_INSTALL_PATTERNS: list[tuple[str, str, str]] = [
    # JS package managers
    (
        r"\bnpm\s+(?:install|i|add|ci)\b",
        "AGENT-RUNTIME-INSTALL-NPM",
        "Course attempts to install an npm package at runtime",
    ),
    (
        r"\b(?:yarn|pnpm)\s+(?:global\s+)?(?:add|install|i)\b",
        "AGENT-RUNTIME-INSTALL-YARN-PNPM",
        "Course attempts to install a yarn/pnpm package at runtime",
    ),
    (
        r"\bbun\s+(?:add|install)\b",
        "AGENT-RUNTIME-INSTALL-BUN",
        "Course attempts to install a bun package at runtime",
    ),
    (
        r"\bdeno\s+install\b",
        "AGENT-RUNTIME-INSTALL-DENO",
        "Course attempts to install a deno script at runtime",
    ),
    (
        r"\bnpx\s+(?:-[-\w]+\s+)*[\w@./-]",
        "AGENT-RUNTIME-INSTALL-NPX",
        "Course executes an npm package fetched at runtime via npx",
    ),
    # Python package managers
    (
        r"\bpip3?\s+install\b",
        "AGENT-RUNTIME-INSTALL-PIP",
        "Course attempts to install a Python package at runtime",
    ),
    (
        r"\bpipx\s+(?:install|run)\b",
        "AGENT-RUNTIME-INSTALL-PIPX",
        "Course attempts to install or run a pipx tool at runtime",
    ),
    (
        r"\buv\s+(?:pip\s+install|tool\s+(?:install|run)|add)\b",
        "AGENT-RUNTIME-INSTALL-UV",
        "Course attempts to install a Python package via uv at runtime",
    ),
    (
        r"\bpython\d?(?:\.\d+)?\s+-m\s+pip\s+install\b",
        "AGENT-RUNTIME-INSTALL-PIP",
        "Course attempts python -m pip install at runtime",
    ),
    (
        r"\bpoetry\s+(?:add|install)\b",
        "AGENT-RUNTIME-INSTALL-POETRY",
        "Course attempts to install a Python package via poetry at runtime",
    ),
    (
        r"\bconda\s+install\b|\bmamba\s+install\b",
        "AGENT-RUNTIME-INSTALL-CONDA",
        "Course attempts to install a conda package at runtime",
    ),
    # System package managers
    (
        r"\bbrew\s+(?:install|tap|bundle)\b",
        "AGENT-RUNTIME-INSTALL-BREW",
        "Course attempts to install a Homebrew package at runtime",
    ),
    (
        r"\bapt(?:-get)?\s+(?:-[-\w]+\s+)*install\b",
        "AGENT-RUNTIME-INSTALL-APT",
        "Course attempts apt/apt-get install at runtime",
    ),
    (
        r"\b(?:dnf|yum)\s+(?:-[-\w]+\s+)*install\b",
        "AGENT-RUNTIME-INSTALL-RPM",
        "Course attempts dnf/yum install at runtime",
    ),
    (
        r"\bpacman\s+-S\w*\b",
        "AGENT-RUNTIME-INSTALL-PACMAN",
        "Course attempts pacman -S at runtime",
    ),
    (
        r"\bapk\s+add\b",
        "AGENT-RUNTIME-INSTALL-APK",
        "Course attempts apk add at runtime",
    ),
    (
        r"\bzypper\s+(?:-[-\w]+\s+)*(?:install|in)\b",
        "AGENT-RUNTIME-INSTALL-ZYPPER",
        "Course attempts zypper install at runtime",
    ),
    (
        r"\bsnap\s+install\b",
        "AGENT-RUNTIME-INSTALL-SNAP",
        "Course attempts snap install at runtime",
    ),
    (
        r"\bflatpak\s+install\b",
        "AGENT-RUNTIME-INSTALL-FLATPAK",
        "Course attempts flatpak install at runtime",
    ),
    (
        r"\bnix(?:-env)?\s+(?:-i\b|profile\s+install\b)",
        "AGENT-RUNTIME-INSTALL-NIX",
        "Course attempts a nix install at runtime",
    ),
    # Windows package managers
    (
        r"\b(?:choco|chocolatey)\s+install\b",
        "AGENT-RUNTIME-INSTALL-CHOCO",
        "Course attempts chocolatey install at runtime",
    ),
    (
        r"\bscoop\s+install\b",
        "AGENT-RUNTIME-INSTALL-SCOOP",
        "Course attempts scoop install at runtime",
    ),
    (
        r"\bwinget\s+install\b",
        "AGENT-RUNTIME-INSTALL-WINGET",
        "Course attempts winget install at runtime",
    ),
    # Language-ecosystem installers
    (
        r"\bcargo\s+install\b",
        "AGENT-RUNTIME-INSTALL-CARGO",
        "Course attempts cargo install at runtime",
    ),
    (
        r"\bgo\s+install\s+[\w@./-]",
        "AGENT-RUNTIME-INSTALL-GO",
        "Course attempts go install at runtime",
    ),
    (
        r"\bgem\s+install\b",
        "AGENT-RUNTIME-INSTALL-GEM",
        "Course attempts gem install at runtime",
    ),
    (
        r"\bcomposer\s+(?:global\s+)?(?:require|install)\b",
        "AGENT-RUNTIME-INSTALL-COMPOSER",
        "Course attempts composer install at runtime",
    ),
    (
        r"\bdotnet\s+tool\s+install\b",
        "AGENT-RUNTIME-INSTALL-DOTNET",
        "Course attempts dotnet tool install at runtime",
    ),
    (
        r"\bcpan(?:m)?\s+(?:install\s+)?[\w:./-]+",
        "AGENT-RUNTIME-INSTALL-CPAN",
        "Course attempts a cpan install at runtime",
    ),
]


class RuntimeInstallAttemptCheck(BaseCheck):
    """Scan for runtime package-manager install attempts in course
    bundles (self-contained bundle rule)."""

    EXPECTED_RULE_IDS: frozenset[str] = frozenset({
        "AGENT-RUNTIME-INSTALL-NPM",
        "AGENT-RUNTIME-INSTALL-YARN-PNPM",
        "AGENT-RUNTIME-INSTALL-BUN",
        "AGENT-RUNTIME-INSTALL-DENO",
        "AGENT-RUNTIME-INSTALL-NPX",
        "AGENT-RUNTIME-INSTALL-PIP",
        "AGENT-RUNTIME-INSTALL-PIPX",
        "AGENT-RUNTIME-INSTALL-UV",
        "AGENT-RUNTIME-INSTALL-POETRY",
        "AGENT-RUNTIME-INSTALL-CONDA",
        "AGENT-RUNTIME-INSTALL-BREW",
        "AGENT-RUNTIME-INSTALL-APT",
        "AGENT-RUNTIME-INSTALL-RPM",
        "AGENT-RUNTIME-INSTALL-PACMAN",
        "AGENT-RUNTIME-INSTALL-APK",
        "AGENT-RUNTIME-INSTALL-ZYPPER",
        "AGENT-RUNTIME-INSTALL-SNAP",
        "AGENT-RUNTIME-INSTALL-FLATPAK",
        "AGENT-RUNTIME-INSTALL-NIX",
        "AGENT-RUNTIME-INSTALL-CHOCO",
        "AGENT-RUNTIME-INSTALL-SCOOP",
        "AGENT-RUNTIME-INSTALL-WINGET",
        "AGENT-RUNTIME-INSTALL-CARGO",
        "AGENT-RUNTIME-INSTALL-GO",
        "AGENT-RUNTIME-INSTALL-GEM",
        "AGENT-RUNTIME-INSTALL-COMPOSER",
        "AGENT-RUNTIME-INSTALL-DOTNET",
        "AGENT-RUNTIME-INSTALL-CPAN",
    })

    name = "runtime-install-attempt"

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

            for line_no, line in enumerate(content.splitlines(), start=1):
                for pattern, rule_id, desc in _INSTALL_PATTERNS:
                    if re.search(pattern, line):
                        findings.append(
                            ScannerFinding(
                                layer=SCANNER_AGENT,
                                severity="high",
                                rule_id=rule_id,
                                description=desc,
                                file_path=rel,
                                line_number=line_no,
                            )
                        )
        return findings

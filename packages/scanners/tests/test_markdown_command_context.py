# SPDX-License-Identifier: MIT
"""Markdown prose must not trigger command-pattern checks.

Regression suite for the gmail-cli dogfood false positives: docs that
*say* "there is no pip install" were flagged as runtime install
attempts. Command patterns in markdown now apply only inside fenced
code blocks; non-markdown files keep full-content scanning.
"""

from __future__ import annotations

from pathlib import Path

from logion_scanners.checks.base import iter_command_lines
from logion_scanners.checks.dangerous_commands import (
    DangerousCommandsCheck,
)
from logion_scanners.checks.runtime_install_attempt import (
    RuntimeInstallAttemptCheck,
)

PROSE_MD = """# Clean Skill

This bundle is self-contained: there is no pip install, no npm install,
and nothing fetched at runtime. We never run rm -rf or sudo anything.
"""

FENCED_MD = """# Setup

Run this first:

```bash
pip install requests
```
"""


def _write_bundle(tmp_path: Path, name: str, content: str) -> Path:
    bundle = tmp_path / name
    bundle.mkdir()
    (bundle / "SKILL.md").write_text(content, encoding="utf-8")
    return bundle


class TestMarkdownProse:
    def test_install_mentions_in_prose_do_not_flag(
        self, tmp_path: Path
    ) -> None:
        bundle = _write_bundle(tmp_path, "prose", PROSE_MD)
        assert RuntimeInstallAttemptCheck().run(bundle) == []

    def test_dangerous_mentions_in_prose_do_not_flag(
        self, tmp_path: Path
    ) -> None:
        bundle = _write_bundle(tmp_path, "prose", PROSE_MD)
        assert DangerousCommandsCheck().run(bundle) == []

    def test_fenced_code_block_still_flags(self, tmp_path: Path) -> None:
        bundle = _write_bundle(tmp_path, "fenced", FENCED_MD)
        rule_ids = {
            f.rule_id for f in RuntimeInstallAttemptCheck().run(bundle)
        }
        assert rule_ids == {"AGENT-RUNTIME-INSTALL-PIP"}

    def test_shell_files_scan_every_line(self, tmp_path: Path) -> None:
        bundle = tmp_path / "shell"
        bundle.mkdir()
        (bundle / "SKILL.md").write_text("# Doc\n", encoding="utf-8")
        (bundle / "setup.sh").write_text(
            "# no fences needed here\npip install requests\n",
            encoding="utf-8",
        )
        rule_ids = {
            f.rule_id for f in RuntimeInstallAttemptCheck().run(bundle)
        }
        assert rule_ids == {"AGENT-RUNTIME-INSTALL-PIP"}


class TestIterCommandLines:
    def test_markdown_yields_only_fenced_lines_with_numbers(self) -> None:
        content = "prose\n```\ncmd one\n```\nmore prose\n~~~\ncmd two\n~~~\n"
        assert list(iter_command_lines(content, ".md")) == [
            (3, "cmd one"),
            (7, "cmd two"),
        ]

    def test_unclosed_fence_scans_to_eof(self) -> None:
        content = "prose\n```\ncmd\n"
        assert list(iter_command_lines(content, ".md")) == [(3, "cmd")]

    def test_non_markdown_yields_all_lines(self) -> None:
        content = "a\nb\n"
        assert list(iter_command_lines(content, ".sh")) == [
            (1, "a"),
            (2, "b"),
        ]

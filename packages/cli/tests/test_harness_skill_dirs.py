# SPDX-License-Identifier: MIT
"""Tests for harness ``skill_dir`` across all registered adapters."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli._harness import adapter_names, detect_present
from cli._harness.claude_code import ClaudeCodeAdapter
from cli._harness.codex import CodexAdapter
from cli._harness.custom import CustomPathHarness
from cli._harness.hermes import HermesAdapter
from cli._harness.opencode import OpenCodeAdapter
from cli._harness.pi import PiAdapter
from cli.commands.skills._agent_symlink import EXAMPLE_AGENT_DIRS


def _make(adapter_cls, tmp_path: Path):
    """Create an adapter with injected home_dir."""
    return adapter_cls(home_dir=tmp_path / "home")


@pytest.mark.parametrize(
    ("adapter_cls", "expected_suffix"),
    [
        (ClaudeCodeAdapter, ".claude/skills"),
        # Codex user scope is the cross-harness .agents/skills;
        # ~/.codex/skills is legacy (detected via legacy_skill_dir()).
        (CodexAdapter, ".agents/skills"),
        (OpenCodeAdapter, ".config/opencode/skills"),
        (HermesAdapter, ".hermes/skills"),
    ],
)
def test_skill_dir_per_harness(
    tmp_path: Path, monkeypatch, adapter_cls, expected_suffix: str
) -> None:
    monkeypatch.delenv("HERMES_HOME", raising=False)
    a = _make(adapter_cls, tmp_path)
    result = a.skill_dir()
    assert result == (tmp_path / "home" / expected_suffix)


def test_codex_prompt_example_matches_adapter_path() -> None:
    examples = dict(EXAMPLE_AGENT_DIRS)
    adapter_path = CodexAdapter(home_dir=Path("~")).skill_dir()
    assert examples["Codex"] == str(adapter_path)


def test_registry_lists_all_five() -> None:
    names = set(adapter_names())
    assert names == {"claude-code", "codex", "opencode", "hermes", "pi"}


def test_detect_present_per_harness(tmp_path: Path, monkeypatch) -> None:
    """Only the harness whose dir exists should be detected."""
    import shutil

    import cli._harness as harness_mod

    monkeypatch.delenv("HERMES_HOME", raising=False)

    # Force all adapters to use our injected home and isolate PATH.
    original_all = harness_mod.all_adapters

    def fake_all():
        kwargs = {
            "home_dir": tmp_path / "home",
            # Isolate cwd-based detection from any real project .claude dir.
            "project_dir": tmp_path / "proj",
        }
        return [
            ClaudeCodeAdapter(**kwargs),
            CodexAdapter(**kwargs),
            OpenCodeAdapter(**kwargs),
            HermesAdapter(**kwargs),
            PiAdapter(**kwargs),
        ]

    harness_mod.all_adapters = fake_all
    original_which = shutil.which
    shutil.which = lambda _name: None  # type: ignore[assignment]
    try:
        (tmp_path / "home" / ".codex").mkdir(parents=True)
        present = detect_present()
        names = [a.name for a in present]
        assert names == ["codex"]
    finally:
        harness_mod.all_adapters = original_all
        shutil.which = original_which  # type: ignore[assignment]


def test_custom_path_harness(tmp_path: Path) -> None:
    custom_dir = tmp_path / "custom"
    h = CustomPathHarness(custom_dir)
    assert h.skill_dir() == custom_dir
    assert h.is_present() is False
    result = h.grant("global")
    assert result.changed is False
    assert result.already is True


def test_claude_code_skill_dir(tmp_path: Path) -> None:
    a = ClaudeCodeAdapter(
        project_dir=tmp_path / "proj",
        home_dir=tmp_path / "home",
    )
    assert a.skill_dir() == tmp_path / "home" / ".claude" / "skills"

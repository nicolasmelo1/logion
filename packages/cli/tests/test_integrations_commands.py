# SPDX-License-Identifier: MIT
"""Tests for integrations CLI commands.

These drive the real adapters against a temporary ``HOME`` rather than a
fake: the thing worth testing is the edit that lands in the user's
harness config, and a fake adapter cannot get that wrong.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._harness import get_adapter
from cli.integrations_state import get_mode, managed_hooks
from cli.main import main

OBSERVE_COMMAND = "logion usage observe"


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway ``HOME`` so adapters edit a temp config, not the user's."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return home


def _settings(home: Path) -> dict[str, object]:
    path = home / ".claude" / "settings.json"
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _hook_commands(settings: dict[str, object]) -> list[str]:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    groups = hooks.get("PostToolUse")
    if not isinstance(groups, list):
        return []
    return [
        entry["command"]
        for group in groups
        if isinstance(group, dict)
        for entry in group.get("hooks", [])
        if isinstance(entry, dict) and isinstance(entry.get("command"), str)
    ]


def test_detect_reports_which_harnesses_can_observe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Detect must distinguish "installed" from "observable"."""
    assert main(["integrations", "detect", "--json"]) == 0
    supported = json.loads(capsys.readouterr().out)["data"]["supported"]
    by_name = {entry["name"]: entry for entry in supported}

    assert by_name["claude-code"]["observation_supported"] is True
    assert by_name["codex"]["observation_supported"] is True
    assert by_name["hermes"]["observation_supported"] is False


def test_enable_dry_run_shows_the_diff_and_writes_nothing(
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The user has to be able to read the edit before consenting to it."""
    assert (
        main([
            "integrations",
            "enable",
            "claude-code",
            "--dry-run",
            "--json",
        ])
        == 0
    )

    data = json.loads(capsys.readouterr().out)["data"]
    assert data["dry_run"] is True
    assert data["plan"]["supported"] is True
    assert OBSERVE_COMMAND in data["plan"]["diff"]
    assert "PostToolUse" in data["plan"]["diff"]
    assert not (fake_home / ".claude" / "settings.json").exists()
    assert get_mode("claude-code") is None


def test_enable_installs_the_hook_and_preserves_user_config(
    fake_home: Path,
) -> None:
    """Logion adds its hook without touching anything it does not own."""
    settings_path = fake_home / ".claude" / "settings.json"
    settings_path.write_text(
        json.dumps({
            "model": "opus",
            "permissions": {"allow": ["Bash(ls:*)"]},
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write",
                        "hooks": [{"type": "command", "command": "./mine.sh"}],
                    }
                ]
            },
        }),
        encoding="utf-8",
    )

    assert (
        main(["integrations", "enable", "claude-code", "--mode", "auto"]) == 0
    )

    settings = _settings(fake_home)
    assert settings["model"] == "opus"
    assert settings["permissions"] == {"allow": ["Bash(ls:*)"]}
    commands = _hook_commands(settings)
    assert "./mine.sh" in commands
    assert any(c.startswith(OBSERVE_COMMAND) for c in commands)
    assert get_mode("claude-code") == "auto"
    recorded = managed_hooks("claude-code")
    assert len(recorded) == 1
    assert recorded[0]["config_path"] == str(settings_path)


def test_enable_is_idempotent(fake_home: Path) -> None:
    """Enabling twice must not stack duplicate hooks."""
    assert main(["integrations", "enable", "claude-code"]) == 0
    first = (fake_home / ".claude" / "settings.json").read_text()

    assert main(["integrations", "enable", "claude-code"]) == 0

    assert (fake_home / ".claude" / "settings.json").read_text() == first
    assert len(_hook_commands(_settings(fake_home))) == 1


def test_disable_removes_only_the_logion_hook(fake_home: Path) -> None:
    """Uninstall is scoped to entries Logion installed."""
    assert main(["integrations", "enable", "claude-code"]) == 0
    settings = _settings(fake_home)
    groups = settings["hooks"]["PostToolUse"]  # type: ignore[index]
    groups[0]["hooks"].append({"type": "command", "command": "./mine.sh"})
    (fake_home / ".claude" / "settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )

    assert main(["integrations", "disable", "claude-code"]) == 0

    commands = _hook_commands(_settings(fake_home))
    assert commands == ["./mine.sh"]
    assert get_mode("claude-code") == "off"
    assert managed_hooks("claude-code") == []


def test_disable_leaves_no_empty_scaffolding(fake_home: Path) -> None:
    """Removing the only hook removes the keys Logion created."""
    assert main(["integrations", "enable", "claude-code"]) == 0
    assert main(["integrations", "disable", "claude-code"]) == 0

    assert "hooks" not in _settings(fake_home)


def test_enable_mode_off_disables(fake_home: Path) -> None:
    """``--mode off`` is a real mode, not an unsupported choice."""
    assert main(["integrations", "enable", "claude-code"]) == 0
    assert (
        main(["integrations", "enable", "claude-code", "--mode", "off"]) == 0
    )

    assert get_mode("claude-code") == "off"
    assert "hooks" not in _settings(fake_home)


def test_codex_hook_goes_to_hooks_json_not_the_toml_config(
    fake_home: Path,
) -> None:
    """Logion writes its own JSON file rather than rewriting user TOML."""
    (fake_home / ".codex" / "config.toml").write_text(
        'model = "gpt-5.4"\n', encoding="utf-8"
    )

    assert main(["integrations", "enable", "codex"]) == 0

    hooks_path = fake_home / ".codex" / "hooks.json"
    assert hooks_path.is_file()
    payload = json.loads(hooks_path.read_text(encoding="utf-8"))
    entry = payload["hooks"]["PostToolUse"][0]["hooks"][0]
    assert entry["command"].startswith(OBSERVE_COMMAND)
    assert entry["async"] is True
    assert (fake_home / ".codex" / "config.toml").read_text() == (
        'model = "gpt-5.4"\n'
    )


@pytest.mark.usefixtures("fake_home")
def test_hermes_reports_explicit_report_fallback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Hermes has no lifecycle hook but supports explicit companion report.

    This is distinct from ``inventory_only``: the companion can produce
    observation records from the agent's own workflow, just not
    automatically via a harness-fired hook.
    """
    assert main(["integrations", "enable", "hermes", "--json"]) == 0

    plan = json.loads(capsys.readouterr().out)["data"]["plan"]
    assert plan["supported"] is True
    assert plan["reason"] == "explicit_report_observation"
    assert plan["path"] is None


def test_enable_refuses_to_clobber_an_unparseable_config(
    fake_home: Path,
) -> None:
    """A config Logion cannot parse is left exactly as it was."""
    settings_path = fake_home / ".claude" / "settings.json"
    settings_path.write_text("{ not json", encoding="utf-8")

    assert main(["integrations", "enable", "claude-code"]) != 0

    assert settings_path.read_text() == "{ not json"


def test_enable_unknown_harness(capsys: pytest.CaptureFixture[str]) -> None:
    """An unknown harness is rejected."""
    assert main(["integrations", "enable", "nope"]) == 2
    assert "Unknown harness" in capsys.readouterr().err


@pytest.mark.usefixtures("fake_home")
def test_status_reports_effective_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Status distinguishes stored consent from what is in force."""
    assert (
        main(["integrations", "enable", "claude-code", "--mode", "auto"]) == 0
    )
    capsys.readouterr()

    assert main(["integrations", "status", "--json"]) == 0
    statuses = {
        entry["name"]: entry
        for entry in json.loads(capsys.readouterr().out)["data"]
    }

    assert statuses["claude-code"]["mode"] == "auto"
    assert statuses["claude-code"]["effective_mode"] == "auto"
    assert statuses["claude-code"]["enabled"] is True
    assert statuses["hermes"]["effective_mode"] == "off"
    assert statuses["hermes"]["enabled"] is False


@pytest.mark.usefixtures("fake_home")
def test_status_flags_do_not_track(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A machine-wide opt-out is visible in status, not silently ignored."""
    assert (
        main(["integrations", "enable", "claude-code", "--mode", "auto"]) == 0
    )
    capsys.readouterr()
    monkeypatch.setenv("DO_NOT_TRACK", "1")

    assert main(["integrations", "status", "--json"]) == 0
    statuses = {
        entry["name"]: entry
        for entry in json.loads(capsys.readouterr().out)["data"]
    }

    assert statuses["claude-code"]["mode"] == "auto"
    assert statuses["claude-code"]["effective_mode"] == "off"
    assert statuses["claude-code"]["enabled"] is False


def test_observation_command_names_its_harness() -> None:
    """The hook has to tell Logion which harness fired it."""
    adapter = get_adapter("claude-code")
    assert adapter is not None
    assert adapter.observation_command() == (
        "logion usage observe --harness claude-code --stdin"
    )

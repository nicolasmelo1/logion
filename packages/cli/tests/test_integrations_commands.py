# SPDX-License-Identifier: MIT
"""Tests for integrations CLI commands."""

from __future__ import annotations

import json

import pytest

from cli.main import main


class FakeAdapter:
    """Fake harness adapter for testing."""

    def __init__(
        self,
        name: str = "codex",
        display_name: str = "Codex",
        present: bool = True,
    ) -> None:
        self.name = name
        self.display_name = display_name
        self._present = present

    def is_present(self) -> bool:
        return self._present


def _patch_adapters(
    monkeypatch: pytest.MonkeyPatch,
    adapters: list[FakeAdapter],
) -> None:
    """Replace the harness registry with fake adapters."""
    monkeypatch.setattr("cli._harness.all_adapters", lambda: list(adapters))
    monkeypatch.setattr(
        "cli._harness.adapter_names", lambda: [a.name for a in adapters]
    )
    monkeypatch.setattr(
        "cli._harness.detect_present",
        lambda: [a for a in adapters if a.is_present()],
    )
    monkeypatch.setattr(
        "cli._harness.get_adapter",
        lambda name: next((a for a in adapters if a.name == name), None),
    )
    # Also patch the imports in the handlers module
    monkeypatch.setattr(
        "cli.commands.integrations.handlers.all_adapters",
        lambda: list(adapters),
    )
    monkeypatch.setattr(
        "cli.commands.integrations.handlers.adapter_names",
        lambda: [a.name for a in adapters],
    )
    monkeypatch.setattr(
        "cli.commands.integrations.handlers.detect_present",
        lambda: [a for a in adapters if a.is_present()],
    )
    monkeypatch.setattr(
        "cli.commands.integrations.handlers.get_adapter",
        lambda name: next((a for a in adapters if a.name == name), None),
    )


def test_integrations_detect_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """integrations detect --json lists detected and supported harnesses."""
    adapters = [
        FakeAdapter("codex", "Codex", present=True),
        FakeAdapter("claude-code", "Claude Code", present=False),
    ]
    _patch_adapters(monkeypatch, adapters)

    assert main(["integrations", "detect", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.integrations.detect"
    assert len(payload["data"]["detected"]) == 1
    assert payload["data"]["detected"][0]["name"] == "codex"
    assert len(payload["data"]["supported"]) == 2


def test_integrations_detect_human_readable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """integrations detect without --json prints detected harnesses."""
    adapters = [FakeAdapter("codex", "Codex", present=True)]
    _patch_adapters(monkeypatch, adapters)

    assert main(["integrations", "detect"]) == 0
    out = capsys.readouterr().out
    assert "codex" in out


def test_integrations_enable_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """integrations enable --json emits the v1 JSON envelope."""
    adapters = [FakeAdapter("codex", "Codex", present=True)]
    _patch_adapters(monkeypatch, adapters)

    assert (
        main([
            "integrations",
            "enable",
            "codex",
            "--mode",
            "auto",
            "--json",
        ])
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.integrations.enable"
    assert payload["data"]["harness"] == "codex"
    assert payload["data"]["mode"] == "auto"
    assert payload["data"]["enabled"] is True


def test_integrations_enable_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """integrations enable --dry-run does not mark as enabled."""
    adapters = [FakeAdapter("codex", "Codex", present=True)]
    _patch_adapters(monkeypatch, adapters)

    assert (
        main(["integrations", "enable", "codex", "--dry-run", "--json"]) == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["enabled"] is False


def test_integrations_enable_unknown_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """integrations enable with unknown harness returns exit code 2."""
    _patch_adapters(monkeypatch, [])

    assert main(["integrations", "enable", "unknown", "--json"]) == 2


def test_integrations_disable_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """integrations disable --json emits the v1 JSON envelope."""
    adapters = [FakeAdapter("codex", "Codex", present=True)]
    _patch_adapters(monkeypatch, adapters)

    assert main(["integrations", "disable", "codex", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.integrations.disable"
    assert payload["data"]["harness"] == "codex"
    assert payload["data"]["disabled"] is True


def test_integrations_disable_unknown_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """integrations disable with unknown harness returns exit code 2."""
    _patch_adapters(monkeypatch, [])

    assert main(["integrations", "disable", "unknown", "--json"]) == 2


def test_integrations_status_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """integrations status --json lists all harnesses with presence."""
    adapters = [
        FakeAdapter("codex", "Codex", present=True),
        FakeAdapter("claude-code", "Claude Code", present=False),
    ]
    _patch_adapters(monkeypatch, adapters)

    assert main(["integrations", "status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.integrations.status"
    assert len(payload["data"]) == 2
    assert payload["data"][0]["name"] == "codex"
    assert payload["data"][0]["present"] is True
    assert payload["data"][1]["present"] is False


def test_integrations_status_human_readable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """integrations status without --json prints human-readable output."""
    adapters = [
        FakeAdapter("codex", "Codex", present=True),
        FakeAdapter("claude-code", "Claude Code", present=False),
    ]
    _patch_adapters(monkeypatch, adapters)

    assert main(["integrations", "status"]) == 0
    out = capsys.readouterr().out
    assert "codex" in out
    assert "disabled" in out

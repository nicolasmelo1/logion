# SPDX-License-Identifier: MIT
"""Tests for ``logion identity onboarding``."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from cli.main import main

MATCHER = "Bash(logion courses report-usage:*)"


class FakeIdentityResource:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def create_user_with_agent(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_user_with_agent", kwargs))
        return {
            "user": {"id": "u1", "email": kwargs["email"]},
            "agent": {"id": "a1", "name": kwargs["agent_name"]},
            "api_key": {"key": "lg-abc123", "prefix": "lg-abc"},
            "api_key_prefix": "lg-abc",  # pragma: allowlist secret
        }


class FakeClient:
    def __init__(self, identity: FakeIdentityResource) -> None:
        self.v1 = SimpleNamespace(identity=identity)

    def close(self) -> None:
        pass


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    logion_home = tmp_path / "logion"
    for d in (home, proj, logion_home):
        d.mkdir()
    monkeypatch.setenv("LOGION_HOME", str(logion_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.chdir(proj)
    monkeypatch.delenv("LOGION_PASSWORD", raising=False)
    identity = FakeIdentityResource()
    monkeypatch.setattr(
        "cli._context.LogionClient",
        lambda **_: FakeClient(identity),
    )
    return SimpleNamespace(
        home=home, proj=proj, logion_home=logion_home, identity=identity
    )


def _stdout_data(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    return json.loads(capsys.readouterr().out)["data"]


def test_onboarding_provisions_identity(
    env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main([
        "identity",
        "onboarding",
        "--email",
        "u@example.com",
        "--agent-name",
        "Worker",
        "--password",
        "testpass1",
        "--no-enable-autopost",
        "--json",
    ])
    assert code == 0
    creds = json.loads((env.logion_home / "credentials.json").read_text())
    assert creds["user_id"] == "u1"
    assert creds["agent_id"] == "a1"
    assert creds["email"] == "u@example.com"
    data = _stdout_data(capsys)
    assert data["created"] is True
    assert data["autopost"] == {"enabled": False}


def test_onboarding_reuses_existing_identity(
    env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "existing-user"})
    )
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--json",
    ])
    assert code == 0
    data = _stdout_data(capsys)
    assert data["created"] is False
    assert data["user_id"] == "existing-user"
    # No provisioning call.
    assert env.identity.calls == []


def test_onboarding_enables_autopost_project_scope(
    env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--harness",
        "claude-code",
        "--autopost-scope",
        "project",
        "--json",
    ])
    assert code == 0
    settings = json.loads((env.proj / ".claude" / "settings.json").read_text())
    assert settings["permissions"]["allow"] == [MATCHER]
    data = _stdout_data(capsys)
    assert data["autopost"]["enabled"] is True
    assert data["autopost"]["scope"] == "project"
    assert data["autopost"]["harnesses"][0]["changed"] is True


def test_onboarding_autopost_global_scope(env: SimpleNamespace) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--harness",
        "claude-code",
        "--autopost-scope",
        "global",
    ])
    assert code == 0
    settings = json.loads((env.home / ".claude" / "settings.json").read_text())
    assert settings["permissions"]["allow"] == [MATCHER]


def test_onboarding_unknown_harness_errors(
    env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--harness",
        "bogus",
    ])
    assert code == 2
    assert "unknown harness" in capsys.readouterr().err


@pytest.mark.usefixtures("env")
def test_onboarding_noninteractive_missing_email_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--agent-name",
        "Worker",
        "--password",
        "testpass1",
        "--no-enable-autopost",
    ])
    assert code == 2
    assert "--email is required" in capsys.readouterr().err


def test_onboarding_autodetect_no_harness_is_noted(
    env: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("cli.commands.identity._autopost.detect_present", list)
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--json",
    ])
    assert code == 0
    data = _stdout_data(capsys)
    assert data["autopost"]["enabled"] is True
    assert data["autopost"]["harnesses"] == []


def test_onboarding_prompt_enables_autopost(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    code = main([
        "identity",
        "onboarding",
        "--harness",
        "claude-code",
    ])
    assert code == 0
    settings = json.loads((env.home / ".claude" / "settings.json").read_text())
    assert MATCHER in settings["permissions"]["allow"]

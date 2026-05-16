"""Tests for the identity commands."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cli.main import main


class FakeIdentityResource:
    """Fake identity resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

    def create_user_with_agent(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create_user_with_agent", kwargs)
        return {
            "user": {"id": "u1", "email": kwargs["email"]},
            "agent": {"id": "a1", "name": kwargs["agent_name"]},
            "api_key": {"key": "lg-abc123", "prefix": "lg-abc"},
        }

    def add_agent_to_user(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("add_agent_to_user", kwargs)
        return {
            "agent": {"id": "a2", "name": kwargs["agent_name"]},
            "api_key": {"key": "lg-def456", "prefix": "lg-def"},
        }

    def rotate_api_key(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("rotate_api_key", kwargs)
        return {
            "api_key": {"key": "lg-xyz789", "prefix": "lg-xyz"},
        }


class FakeV1Namespace:
    def __init__(self, identity: FakeIdentityResource) -> None:
        self.identity = identity


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_users_create_calls_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """identity users-create forwards args to SDK."""
    monkeypatch.delenv("LOGION_PASSWORD", raising=False)
    identity = FakeIdentityResource()
    fake = FakeClient(v1=FakeV1Namespace(identity=identity))
    _patch_client(monkeypatch, fake)
    code = main([
        "identity",
        "users-create",
        "--email",
        "user@example.com",
        "--password",
        "testpass1",
        "--agent-name",
        "My Agent",
        "--user-name",
        "Nicolas",
        "--agent-description",
        "Local agent",
        "--json",
    ])
    assert code == 0
    method, kwargs = identity.last_call
    assert method == "create_user_with_agent"
    assert kwargs["email"] == "user@example.com"
    assert kwargs["user_password"] == "testpass1"  # pragma: allowlist secret
    assert kwargs["agent_name"] == "My Agent"
    assert kwargs["user_name"] == "Nicolas"
    assert kwargs["agent_description"] == "Local agent"
    data = json.loads(capsys.readouterr().out)
    assert data["user"]["email"] == "user@example.com"


def test_users_create_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """identity users-create reads LOGION_PASSWORD when --password omitted."""
    monkeypatch.setenv("LOGION_PASSWORD", "envpass1")
    identity = FakeIdentityResource()
    fake = FakeClient(v1=FakeV1Namespace(identity=identity))
    _patch_client(monkeypatch, fake)
    code = main([
        "identity",
        "users-create",
        "--email",
        "user@example.com",
        "--agent-name",
        "TestAgent",
        "--json",
    ])
    assert code == 0
    _method, kwargs = identity.last_call
    assert kwargs["user_password"] == "envpass1"  # pragma: allowlist secret


def test_users_create_minimal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """identity users-create with only required args."""
    monkeypatch.delenv("LOGION_PASSWORD", raising=False)
    identity = FakeIdentityResource()
    fake = FakeClient(v1=FakeV1Namespace(identity=identity))
    _patch_client(monkeypatch, fake)
    code = main([
        "identity",
        "users-create",
        "--email",
        "user@example.com",
        "--password",
        "testpass1",
        "--agent-name",
        "TestAgent",
        "--json",
    ])
    assert code == 0
    method, kwargs = identity.last_call
    assert method == "create_user_with_agent"
    assert kwargs["user_name"] is None
    assert kwargs["agent_description"] is None


def test_agents_add_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """identity agents-add forwards args to SDK."""
    monkeypatch.delenv("LOGION_PASSWORD", raising=False)
    identity = FakeIdentityResource()
    fake = FakeClient(v1=FakeV1Namespace(identity=identity))
    _patch_client(monkeypatch, fake)
    code = main([
        "identity",
        "agents-add",
        "--user-id",
        "u1",
        "--agent-name",
        "Worker",
        "--password",
        "testpass1",
        "--agent-description",
        "Handles tasks",
        "--json",
    ])
    assert code == 0
    method, kwargs = identity.last_call
    assert method == "add_agent_to_user"
    assert kwargs["user_id"] == "u1"
    assert kwargs["agent_name"] == "Worker"
    assert kwargs["user_password"] == "testpass1"  # pragma: allowlist secret
    assert kwargs["agent_description"] == "Handles tasks"


def test_agents_rotate_key_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """identity agents-rotate-key forwards args to SDK."""
    monkeypatch.delenv("LOGION_PASSWORD", raising=False)
    identity = FakeIdentityResource()
    fake = FakeClient(v1=FakeV1Namespace(identity=identity))
    _patch_client(monkeypatch, fake)
    code = main([
        "identity",
        "agents-rotate-key",
        "--user-id",
        "u1",
        "--agent-id",
        "a1",
        "--password",
        "testpass1",
        "--json",
    ])
    assert code == 0
    method, kwargs = identity.last_call
    assert method == "rotate_api_key"
    assert kwargs["user_id"] == "u1"
    assert kwargs["agent_id"] == "a1"
    assert kwargs["user_password"] == "testpass1"  # pragma: allowlist secret


def test_users_create_missing_required() -> None:
    """identity users-create fails without required args."""
    with pytest.raises(SystemExit):
        main(["identity", "users-create"])


def test_agents_add_missing_required() -> None:
    """identity agents-add fails without required args."""
    with pytest.raises(SystemExit):
        main(["identity", "agents-add"])


def test_users_create_missing_password_no_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """identity users-create fails without --password or LOGION_PASSWORD."""
    monkeypatch.delenv("LOGION_PASSWORD", raising=False)
    code = main([
        "identity",
        "users-create",
        "--email",
        "user@example.com",
        "--agent-name",
        "TestAgent",
    ])
    assert code == 2


def test_users_create_empty_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """identity users-create rejects empty --password without fallback."""
    monkeypatch.delenv("LOGION_PASSWORD", raising=False)
    code = main([
        "identity",
        "users-create",
        "--email",
        "user@example.com",
        "--agent-name",
        "TestAgent",
        "--password",
        "   ",
    ])
    assert code == 2


def test_users_create_api_key_warning_non_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-JSON output includes API key save warning on stderr."""
    monkeypatch.delenv("LOGION_PASSWORD", raising=False)
    identity = FakeIdentityResource()
    fake = FakeClient(v1=FakeV1Namespace(identity=identity))
    _patch_client(monkeypatch, fake)
    code = main([
        "identity",
        "users-create",
        "--email",
        "user@example.com",
        "--password",
        "testpass1",
        "--agent-name",
        "TestAgent",
    ])
    assert code == 0
    stderr = capsys.readouterr().err
    assert "will not be shown again" in stderr


def test_users_create_env_password_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """identity users-create strips whitespace from LOGION_PASSWORD."""
    monkeypatch.setenv("LOGION_PASSWORD", "  envpass1  ")
    identity = FakeIdentityResource()
    fake = FakeClient(v1=FakeV1Namespace(identity=identity))
    _patch_client(monkeypatch, fake)
    code = main([
        "identity",
        "users-create",
        "--email",
        "user@example.com",
        "--agent-name",
        "TestAgent",
        "--json",
    ])
    assert code == 0
    _method, kwargs = identity.last_call
    assert kwargs["user_password"] == "envpass1"  # pragma: allowlist secret


def test_users_create_env_password_whitespace_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """identity users-create fails when LOGION_PASSWORD is whitespace-only."""
    monkeypatch.setenv("LOGION_PASSWORD", "   ")
    code = main([
        "identity",
        "users-create",
        "--email",
        "user@example.com",
        "--agent-name",
        "TestAgent",
    ])
    assert code == 2

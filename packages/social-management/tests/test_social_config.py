"""Tests for SocialConfig."""

from __future__ import annotations

import pytest

from social_management.core.config import SocialConfig
from social_management.core.errors import MissingCredentialsError


def test_from_env_loads_webhooks(env, tmp_path) -> None:  # type: ignore[no-untyped-def]
    env(DISCORD_WEBHOOK_GENERAL="https://discord.com/api/webhooks/123")
    config = SocialConfig.from_env(env_local=tmp_path / "nonexistent")
    assert config.discord_webhooks["general"].endswith("123")


def test_env_local_does_not_override_shell(
    env,
    tmp_path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    env(X_BACKEND="off")
    env_local = tmp_path / ".env.local"
    env_local.write_text("X_BACKEND=api\n")
    monkeypatch.chdir(tmp_path)
    config = SocialConfig.from_env(env_local=env_local)
    assert config.x_backend == "off"


def test_x_is_live_false_without_creds(env, tmp_path) -> None:  # type: ignore[no-untyped-def]
    env(X_BACKEND="api")
    config = SocialConfig.from_env(env_local=tmp_path / "nope")
    assert config.x_is_live() is False


def test_x_is_live_true_with_oauth1(env, tmp_path) -> None:  # type: ignore[no-untyped-def]
    env(
        X_BACKEND="api",
        X_API_KEY="k",
        X_API_SECRET="s",
        X_ACCESS_TOKEN="t",
        X_ACCESS_SECRET="ts",  # pragma: allowlist secret
    )
    config = SocialConfig.from_env(env_local=tmp_path / "nope")
    assert config.x_is_live() is True


def test_webhook_for_missing_raises(
    env,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    config = SocialConfig.from_env(env_local=tmp_path / "nope")
    with pytest.raises(MissingCredentialsError):
        config.webhook_for("general")

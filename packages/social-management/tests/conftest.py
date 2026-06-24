"""Shared fixtures for social-management tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

ENV_KEYS = [
    "DISCORD_BOT_TOKEN",
    "DISCORD_GUILD_ID",
    "DISCORD_CHANNEL_SUPPORT",
    "DISCORD_WEBHOOK_ANNOUNCEMENTS",
    "DISCORD_WEBHOOK_GENERAL",
    "DISCORD_WEBHOOK_SUPPORT",
    "DISCORD_WEBHOOK_CREATORS",
    "X_BACKEND",
    "X_API_KEY",
    "X_API_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_SECRET",
    "X_BEARER_TOKEN",
    "X_MONTHLY_BUDGET_CENTS",
]


@pytest.fixture()
def env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Clear all DISCORD_*/X_* env vars, return a setter."""

    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    def _set(**kwargs: str) -> None:
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)

    return _set


@pytest.fixture()
def tmp_ledger(tmp_path: Path):  # type: ignore[no-untyped-def]
    """A SpendLedger pointing at a tmp file."""
    from social_management.cost.ledger import SpendLedger

    return SpendLedger(tmp_path / ".spend-ledger.json")


@pytest.fixture()
def tmp_content_dir(tmp_path: Path) -> Path:
    """An empty content/ directory under tmp_path."""
    d = tmp_path / "content"
    d.mkdir()
    return d


@pytest.fixture()
def respx_mock():  # type: ignore[no-untyped-def]
    """respx mock with assert_all_called=False."""
    import respx

    with respx.mock(assert_all_called=False) as mock:
        yield mock

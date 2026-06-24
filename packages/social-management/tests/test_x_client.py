"""Tests for XClient."""

from __future__ import annotations

import httpx
import pytest

from social_management.config import SocialConfig
from social_management.cost import SpendLedger
from social_management.errors import (
    BudgetExceededError,
    ConfirmationRequiredError,
    MissingCredentialsError,
)
from social_management.models import CostEstimate
from social_management.x_client import X_API, XClient


def _live_config(
    env,
    tmp_path,
    budget: int = 1000,  # type: ignore[no-untyped-def]
) -> SocialConfig:
    env(
        X_BACKEND="api",
        X_API_KEY="k",
        X_API_SECRET="s",
        X_ACCESS_TOKEN="t",
        X_ACCESS_SECRET="ts",
        X_MONTHLY_BUDGET_CENTS=str(budget),
    )
    return SocialConfig.from_env(env_local=tmp_path / "nope")


def test_post_dry_run_no_network_returns_cost(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _live_config(env, tmp_path)
    ledger = SpendLedger(tmp_path / ".spend-ledger.json")
    client = XClient(config, ledger=ledger)
    result = client.post("hi", dry_run=True)
    assert result.sent is False
    assert result.cost_cents == 2
    assert result.rendered == "hi"
    assert respx_mock.calls.call_count == 0


def test_post_without_confirm_raises(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _live_config(env, tmp_path)
    ledger = SpendLedger(tmp_path / ".spend-ledger.json")
    client = XClient(config, ledger=ledger)
    with pytest.raises(ConfirmationRequiredError):
        client.post("hi", confirm=False)
    assert respx_mock.calls.call_count == 0


def test_post_with_confirm_sends_and_records(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _live_config(env, tmp_path)
    ledger = SpendLedger(tmp_path / ".spend-ledger.json")
    route = respx_mock.post(X_API).mock(
        return_value=httpx.Response(201, json={"data": {"id": "123"}})
    )
    client = XClient(config, ledger=ledger)
    result = client.post("hi", confirm=True)
    assert result.sent is True
    assert result.remote_id == "123"
    assert route.called
    assert ledger.month_to_date_cents() == 2


def test_post_budget_exceeded_blocks_before_network(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _live_config(env, tmp_path, budget=1)
    ledger = SpendLedger(tmp_path / ".spend-ledger.json")
    # Seed ledger so a 2c post exceeds a 1c cap.
    ledger.record(CostEstimate(cents=2, has_link=False, reason="seed"))
    client = XClient(config, ledger=ledger)
    with pytest.raises(BudgetExceededError):
        client.post("hi", confirm=True)
    assert respx_mock.calls.call_count == 0


def test_backend_off_falls_back_to_manual_render(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    env(X_BACKEND="off")
    config = SocialConfig.from_env(env_local=tmp_path / "nope")
    ledger = SpendLedger(tmp_path / ".spend-ledger.json")
    client = XClient(config, ledger=ledger)
    result = client.post("hi", confirm=True)
    assert result.sent is False
    assert result.note is not None
    assert "manual" in result.note
    assert respx_mock.calls.call_count == 0


def test_link_post_is_flagged_expensive(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    config = _live_config(env, tmp_path)
    ledger = SpendLedger(tmp_path / ".spend-ledger.json")
    client = XClient(config, ledger=ledger)
    result = client.post("buy https://x.com", dry_run=True)
    assert result.cost_cents == 20


def test_api_backend_no_creds_raises(
    env,
    tmp_path,
    respx_mock,  # type: ignore[no-untyped-def]
) -> None:
    """X_BACKEND=api with no credentials should raise, not silently
    fall back."""
    env(X_BACKEND="api")
    config = SocialConfig.from_env(env_local=tmp_path / "nope")
    ledger = SpendLedger(tmp_path / ".spend-ledger.json")
    client = XClient(config, ledger=ledger)
    with pytest.raises(MissingCredentialsError):
        client.post("hi", dry_run=True)

# SPDX-License-Identifier: MIT
"""Tests for the payments commands."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cli.main import main


class FakePaymentsResource:
    """Fake payments resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

    def get_seller_readiness(self) -> dict[str, Any]:
        self.last_call = ("get_seller_readiness", {})
        return {"ready": True, "charges_enabled": True}

    def create_onboarding_link(self) -> dict[str, Any]:
        self.last_call = ("create_onboarding_link", {})
        return {"url": "https://stripe.example.com/onboard"}

    def get_order(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_order", kwargs)
        return {"id": kwargs["order_id"], "status": "paid"}

    def request_cash_out(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("request_cash_out", kwargs)
        return {
            "dry_run": kwargs.get("dry_run", False),
            "amount_cents": 1000,
            "minimum_payout_cents": kwargs.get("minimum_payout_cents"),
        }

    def get_creator_earnings(self) -> dict[str, Any]:
        self.last_call = ("get_creator_earnings", {})
        return {"available_cents": 1000}


class FakeV1Namespace:
    def __init__(self, payments: Any) -> None:
        self.payments = payments


class FakeClient:
    def __init__(self, v1: Any) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: Any) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_seller_readiness(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """payments seller-readiness calls SDK."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)
    assert main(["payments", "seller-readiness", "--json"]) == 0
    method, _kwargs = payments.last_call
    assert method == "get_seller_readiness"
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == "v1"
    assert data["kind"] == "logion.payments.seller-readiness"
    assert data["data"]["ready"] is True


def test_onboarding_link(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """payments onboarding-link calls SDK."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)
    assert main(["payments", "onboarding-link", "--json"]) == 0
    method, _kwargs = payments.last_call
    assert method == "create_onboarding_link"
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == "v1"
    assert data["kind"] == "logion.payments.onboarding-link"
    assert "url" in data["data"]


def test_orders_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """payments orders get forwards order_id."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)
    assert (
        main(
            [
                "payments",
                "orders",
                "get",
                "880e8400-e29b-41d4-a716-446655440003",
                "--json",
            ],
        )
        == 0
    )
    method, kwargs = payments.last_call
    assert method == "get_order"
    assert kwargs["order_id"] == "880e8400-e29b-41d4-a716-446655440003"


def test_orders_get_empty_id() -> None:
    """payments orders get rejects empty order_id."""
    code = main(["payments", "orders", "get", "", "--json"])
    assert code == 2


def test_orders_get_invalid_uuid() -> None:
    """payments orders get rejects an invalid UUID."""
    code = main(["payments", "orders", "get", "not-a-uuid", "--json"])
    assert code == 2


def test_cash_out_non_dry_run_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """payments cash-out without --yes and without --dry-run refuses."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)

    code = main(["payments", "cash-out", "--json"])

    assert code == 2
    assert payments.last_call == ("", {})
    assert "--yes" in capsys.readouterr().err


def test_cash_out_dry_run_does_not_require_yes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """payments cash-out --dry-run runs without --yes."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)

    code = main(["payments", "cash-out", "--dry-run", "--json"])

    assert code == 0
    method, kwargs = payments.last_call
    assert method == "request_cash_out"
    assert kwargs["dry_run"] is True
    capsys.readouterr()


def test_cash_out_yes_runs_non_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """payments cash-out --yes initiates the non-dry-run transfer."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)

    code = main(["payments", "cash-out", "--yes", "--json"])

    assert code == 0
    method, kwargs = payments.last_call
    assert method == "request_cash_out"
    assert kwargs["dry_run"] is False
    capsys.readouterr()

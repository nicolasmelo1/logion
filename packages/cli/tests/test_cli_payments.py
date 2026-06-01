# SPDX-License-Identifier: MIT
"""Tests for the payments commands."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest

from cli.main import main
from logion.v1._types.generated.v1 import CourseCheckoutResponse


def _make_paid_checkout_response(**overrides: Any) -> CourseCheckoutResponse:
    defaults: dict[str, Any] = {
        "amount_cents": 5000,
        "checkout_required": True,
        "checkout_session_id": "cs_test_123",
        "checkout_url": "https://checkout.stripe.example.com/pay",
        "currency": "USD",
        "entitlement_granted": False,
        "marketplace_fee_cents": 500,
        "order_id": UUID("880e8400-e29b-41d4-a716-446655440003"),
        "order_reference": "ord_123",
        "order_status": "checkout_pending",
        "purchase_flow": "stripe_checkout",
        "seller_net_amount_cents": 4500,
    }
    defaults.update(overrides)
    return CourseCheckoutResponse(**defaults)


def _make_free_checkout_response(**overrides: Any) -> CourseCheckoutResponse:
    defaults: dict[str, Any] = {
        "amount_cents": 0,
        "checkout_required": False,
        "checkout_session_id": None,
        "checkout_url": None,
        "currency": "USD",
        "entitlement_granted": True,
        "marketplace_fee_cents": 0,
        "order_id": UUID("00000000-0000-0000-0000-000000000001"),
        "order_reference": "ord_free",
        "order_status": "fulfilled",
        "purchase_flow": "free",
        "seller_net_amount_cents": 0,
    }
    defaults.update(overrides)
    return CourseCheckoutResponse(**defaults)


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

    def create_checkout(self, **kwargs: Any) -> CourseCheckoutResponse:
        self.last_call = ("create_checkout", kwargs)
        return _make_paid_checkout_response()

    def get_order(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_order", kwargs)
        return {"id": kwargs["order_id"], "status": "paid"}


class FakePaymentsResourceFree:
    """Fake payments resource returning a free-flow response."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

    def get_seller_readiness(self) -> dict[str, Any]:
        self.last_call = ("get_seller_readiness", {})
        return {"ready": True, "charges_enabled": True}

    def create_onboarding_link(self) -> dict[str, Any]:
        self.last_call = ("create_onboarding_link", {})
        return {"url": "https://stripe.example.com/onboard"}

    def create_checkout(self, **kwargs: Any) -> CourseCheckoutResponse:
        self.last_call = ("create_checkout", kwargs)
        return _make_free_checkout_response()

    def get_order(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_order", kwargs)
        return {"id": kwargs["order_id"], "status": "paid"}


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


def test_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """payments checkout forwards course_id."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)
    assert (
        main(
            [
                "payments",
                "checkout",
                "550e8400-e29b-41d4-a716-446655440000",
                "--json",
            ],
        )
        == 0
    )
    method, kwargs = payments.last_call
    assert method == "create_checkout"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_checkout_forwards_price_cents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """payments checkout forwards --price-cents."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)
    assert (
        main(
            [
                "payments",
                "checkout",
                "550e8400-e29b-41d4-a716-446655440000",
                "--price-cents",
                "5000",
                "--json",
            ],
        )
        == 0
    )
    method, kwargs = payments.last_call
    assert method == "create_checkout"
    assert kwargs["price_cents"] == 5000


def test_checkout_free_flow_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """payments checkout --json preserves free flow payload."""
    payments = FakePaymentsResourceFree()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)
    assert (
        main(
            [
                "payments",
                "checkout",
                "550e8400-e29b-41d4-a716-446655440000",
                "--json",
            ],
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["purchase_flow"] == "free"
    assert payload["checkout_required"] is False
    assert payload["checkout_url"] is None


def test_checkout_free_flow_human_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """payments checkout human output for free flow has no checkout_url."""
    payments = FakePaymentsResourceFree()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)
    assert (
        main(
            [
                "payments",
                "checkout",
                "550e8400-e29b-41d4-a716-446655440000",
            ],
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "purchase_flow: free" in output
    assert "checkout_required: false" in output
    assert "entitlement_granted: true" in output
    assert "checkout_url:" not in output
    assert "https://checkout.stripe.example.com" not in output


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


def test_checkout_empty_id() -> None:
    """payments checkout rejects empty course_id."""
    code = main(["payments", "checkout", "", "--json"])
    assert code == 2


def test_checkout_invalid_uuid() -> None:
    """payments checkout rejects an invalid UUID."""
    code = main(["payments", "checkout", "not-a-uuid", "--json"])
    assert code == 2


def test_orders_get_invalid_uuid() -> None:
    """payments orders get rejects an invalid UUID."""
    code = main(["payments", "orders", "get", "not-a-uuid", "--json"])
    assert code == 2

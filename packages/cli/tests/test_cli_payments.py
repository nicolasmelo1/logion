"""Tests for the payments commands."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cli.main import main


class FakePaymentsResource:
    """Fake payments resource."""

    def __init__(self) -> None:
        self.last_call: dict[str, Any] = {}

    def get_seller_readiness(self) -> dict[str, Any]:
        self.last_call = ("get_seller_readiness", {})
        return {"ready": True, "charges_enabled": True}

    def create_onboarding_link(self) -> dict[str, Any]:
        self.last_call = ("create_onboarding_link", {})
        return {"url": "https://stripe.example.com/onboard"}

    def create_checkout(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create_checkout", kwargs)
        return {
            "checkout_url": "https://stripe.example.com/pay",
            "order_id": "o1",
        }

    def get_order(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_order", kwargs)
        return {"id": kwargs["order_id"], "status": "paid"}


class FakeV1Namespace:
    def __init__(self, payments: FakePaymentsResource) -> None:
        self.payments = payments


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
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
    assert data["ready"] is True


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
    assert "url" in data


def test_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """payments checkout forwards course_id."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)
    assert main(["payments", "checkout", "c1", "--json"]) == 0
    method, kwargs = payments.last_call
    assert method == "create_checkout"
    assert kwargs["course_id"] == "c1"


def test_orders_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """payments orders get forwards order_id."""
    payments = FakePaymentsResource()
    fake = FakeClient(v1=FakeV1Namespace(payments=payments))
    _patch_client(monkeypatch, fake)
    assert main(["payments", "orders", "get", "o1", "--json"]) == 0
    method, kwargs = payments.last_call
    assert method == "get_order"
    assert kwargs["order_id"] == "o1"

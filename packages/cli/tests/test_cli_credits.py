# SPDX-License-Identifier: MIT
"""Tests for credits CLI commands."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cli.main import main


class FakeCreditsResource:
    """Fake credits resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})
        self.top_up_sequence: list[dict[str, Any]] = []

    def get_balance(self) -> dict[str, Any]:
        self.last_call = ("get_balance", {})
        return {"balance_cents": 700, "currency_code": "USD_CREDIT"}

    def create_top_up(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create_top_up", kwargs)
        return {
            "top_up_id": "11111111-1111-1111-1111-111111111111",
            "status": "pending",
            "amount_cents": kwargs["amount_cents"],
            "credit_cents_granted": kwargs["amount_cents"],
            "checkout_url": "https://checkout.stripe.test/session/topup",
            "stripe_checkout_session_id": "cs_test_123",
        }

    def get_top_up(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_top_up", kwargs)
        if self.top_up_sequence:
            payload = self.top_up_sequence.pop(0)
        else:
            payload = {"status": "paid"}
        return {
            "top_up_id": kwargs["top_up_id"],
            "amount_cents": 1000,
            "credit_cents_granted": 1000,
            "checkout_url": None,
            "stripe_checkout_session_id": "cs_test_123",
            **payload,
        }

    def list_ledger(self) -> list[dict[str, Any]]:
        self.last_call = ("list_ledger", {})
        return [
            {
                "id": "ledger-1",
                "kind": "credit_top_up",
                "direction": "credit",
                "amount_cents": 1000,
                "balance_after_cents": 1000,
                "posted_at": "2026-06-01T00:00:00Z",
            }
        ]


class FakeV1Namespace:
    def __init__(self, credits_resource: FakeCreditsResource) -> None:
        self.credits = credits_resource


class FakeClient:
    def __init__(self, credits_resource: FakeCreditsResource) -> None:
        self.v1 = FakeV1Namespace(credits_resource)
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    credits_resource: FakeCreditsResource,
) -> FakeClient:
    fake = FakeClient(credits_resource)
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)
    return fake


def _decode_json_stream(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    index = 0
    items: list[dict[str, Any]] = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        item, index = decoder.raw_decode(text, index)
        items.append(item)
    return items


def test_credits_balance_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credits balance emits the v1 JSON envelope."""
    credits_resource = FakeCreditsResource()
    _patch_client(monkeypatch, credits_resource)

    assert main(["credits", "balance", "--json"]) == 0

    assert credits_resource.last_call == ("get_balance", {})
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.credits.balance"
    assert payload["data"]["balance_cents"] == 700


def test_credits_top_up_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credits top-up refuses to create checkout without --yes."""
    credits_resource = FakeCreditsResource()
    _patch_client(monkeypatch, credits_resource)

    assert main(["credits", "top-up", "--amount", "1000"]) == 2

    assert credits_resource.last_call == ("", {})
    assert "--yes" in capsys.readouterr().err


def test_credits_top_up_json_forwards_amount_with_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credits top-up --yes forwards amount and renders checkout URL."""
    credits_resource = FakeCreditsResource()
    fake = _patch_client(monkeypatch, credits_resource)

    assert (
        main(["credits", "top-up", "--amount", "1000", "--yes", "--json"]) == 0
    )

    assert credits_resource.last_call == (
        "create_top_up",
        {"amount_cents": 1000},
    )
    assert fake.closed is True
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.credits.top-up"
    assert payload["data"]["checkout_url"].startswith("https://checkout")


def test_credits_top_up_wait_polls_until_paid(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credits top-up --wait polls and emits a final successful wait result."""
    credits_resource = FakeCreditsResource()
    credits_resource.top_up_sequence = [
        {"status": "pending"},
        {"status": "paid"},
    ]
    _patch_client(monkeypatch, credits_resource)
    monkeypatch.setattr(
        "cli.commands.credits.handlers.time.sleep",
        lambda _: None,
    )

    assert (
        main([
            "credits",
            "top-up",
            "--amount",
            "1000",
            "--yes",
            "--wait",
            "--json",
        ])
        == 0
    )

    payloads = _decode_json_stream(capsys.readouterr().out)
    assert payloads[0]["kind"] == "logion.credits.top-up"
    assert payloads[-1]["kind"] == "logion.credits.top-ups.wait"
    assert payloads[-1]["data"]["status"] == "paid"
    assert payloads[-1]["data"]["terminal"] is True


def test_credits_top_ups_get_validates_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """credits top-ups get rejects unsafe identifiers before SDK calls."""
    credits_resource = FakeCreditsResource()
    _patch_client(monkeypatch, credits_resource)

    assert main(["credits", "top-ups", "get", "not-a-uuid", "--json"]) == 2

    assert credits_resource.last_call == ("", {})


def test_credits_ledger_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credits ledger emits the v1 JSON envelope."""
    credits_resource = FakeCreditsResource()
    _patch_client(monkeypatch, credits_resource)

    assert main(["credits", "ledger", "--json"]) == 0

    assert credits_resource.last_call == ("list_ledger", {})
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.credits.ledger"
    assert payload["data"][0]["id"] == "ledger-1"

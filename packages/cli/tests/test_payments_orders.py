# SPDX-License-Identifier: MIT
"""Tests for payments orders get envelope."""

from __future__ import annotations

import argparse
import json
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from cli._config import CliConfig
from cli.commands.payments.handlers import handle_orders_get
from logion.v1._types.generated.v1 import OrderResponse


def _decode_json_stream(text: str) -> list[dict[str, object]]:
    decoder = json.JSONDecoder()
    index = 0
    items: list[dict[str, object]] = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        item, index = decoder.raw_decode(text, index)
        items.append(item)
    return items


def _make_order_response(**overrides: object) -> OrderResponse:
    defaults: dict[str, object] = {
        "amount_cents": 5000,
        "buyer_agent_id": UUID("00000000-0000-0000-0000-000000000001"),
        "course_id": UUID("00000000-0000-0000-0000-000000000002"),
        "currency": "USD_CREDIT",
        "id": UUID("880e8400-e29b-41d4-a716-446655440003"),
        "marketplace_fee_cents": 500,
        "public_reference": "ord_123",
        "seller_agent_id": UUID("00000000-0000-0000-0000-000000000004"),
        "seller_net_amount_cents": 4500,
        "status": "fulfilled",
        "paid_at": "2026-05-28T12:00:00Z",
        "purchase_flow": "credits",
        "balance_before_cents": 10000,
        "balance_after_cents": 5000,
    }
    defaults.update(overrides)
    return OrderResponse(**defaults)  # type: ignore[arg-type]


def _make_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "order_id": "880e8400-e29b-41d4-a716-446655440003",
        "json_output": True,
        "api_key": None,
        "base_url": None,
        "timeout": 120,
        "interval": 5,
        "max_retries": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _default_config(**overrides: object) -> CliConfig:
    defaults: dict[str, object] = {
        "api_key": None,
        "base_url": "https://api.logion.sh",
        "json_output": True,
        "timeout": None,
        "max_retries": None,
    }
    defaults.update(overrides)
    return CliConfig(**defaults)  # type: ignore[arg-type]


def _mock_client_with_orders(sequence: list[object]) -> MagicMock:
    mock_payments = MagicMock()
    mock_payments.get_order = MagicMock(side_effect=sequence)
    mock_v1 = MagicMock()
    mock_v1.payments = mock_payments
    mock_client = MagicMock()
    mock_client.v1 = mock_v1
    mock_client.close = MagicMock()
    return mock_client


def test_orders_get_json_envelope_v1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    order = _make_order_response()
    mock_client = _mock_client_with_orders([order])

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
    ):
        rc = handle_orders_get(_make_args())

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.payments.orders.get"
    assert (
        payload["data"]["order_id"] == "880e8400-e29b-41d4-a716-446655440003"
    )


def test_orders_get_includes_status_field(
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_client = _mock_client_with_orders([
        _make_order_response(status="fulfilled")
    ])

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
    ):
        rc = handle_orders_get(_make_args())

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["status"] == "fulfilled"


def test_orders_get_includes_credit_purchase_fields_when_fulfilled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    order = _make_order_response()
    mock_client = _mock_client_with_orders([order])

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
    ):
        rc = handle_orders_get(_make_args())

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["purchase_flow"] == "credits"
    assert payload["data"]["balance_before_cents"] == 10000
    assert payload["data"]["balance_after_cents"] == 5000
    assert payload["data"]["settled_at"] == "2026-05-28T12:00:00Z"


def test_orders_get_unsafe_order_id_returns_unsafe_identifier_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = handle_orders_get(_make_args(order_id="not-a-uuid"))
    assert rc == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["data"]["code"] == "unsafe_identifier"

# SPDX-License-Identifier: MIT
"""Tests for payments orders get envelope and orders wait subcommand."""

from __future__ import annotations

import argparse
import json
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from cli._config import CliConfig
from cli.commands.payments.handlers import (
    handle_orders_get,
    handle_payments_orders_wait,
)
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
        "currency": "USD",
        "id": UUID("880e8400-e29b-41d4-a716-446655440003"),
        "marketplace_fee_cents": 500,
        "public_reference": "ord_123",
        "seller_agent_id": UUID("00000000-0000-0000-0000-000000000004"),
        "seller_net_amount_cents": 4500,
        "status": "paid",
        "paid_at": "2026-05-28T12:00:00Z",
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
        _make_order_response(status="paid")
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
    assert payload["data"]["status"] == "paid"


def test_orders_get_includes_entitlement_id_when_paid(
    capsys: pytest.CaptureFixture[str],
) -> None:
    order = _make_order_response(
        entitlement_id="ent_123",
        version_id="ver_456",
        checkout_url="https://checkout.example.test",
        created_at="2026-05-28T11:00:00Z",
    )
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
    assert payload["data"]["entitlement_id"] == "ent_123"
    assert payload["data"]["version_id"] == "ver_456"
    assert payload["data"]["checkout_url"] == "https://checkout.example.test"
    assert payload["data"]["settled_at"] == "2026-05-28T12:00:00Z"


def test_orders_get_unsafe_order_id_returns_unsafe_identifier_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = handle_orders_get(_make_args(order_id="not-a-uuid"))
    assert rc == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["data"]["code"] == "unsafe_identifier"


def test_orders_wait_returns_zero_when_paid_within_timeout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    pending = _make_order_response(status="pending", paid_at=None)
    paid = _make_order_response(status="paid")
    mock_client = _mock_client_with_orders([pending, paid])
    fake_time = MagicMock()
    fake_time.monotonic.side_effect = [0.0, 0.0, 1.0, 1.0, 1.0]
    fake_time.sleep = MagicMock()

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch("cli.commands.payments.handlers.time", fake_time),
    ):
        rc = handle_payments_orders_wait(_make_args(timeout=120, interval=5))

    assert rc == 0
    outputs = [
        json.loads(chunk)
        for chunk in capsys.readouterr().out.strip().split("\n\n")
    ]
    assert outputs[-1]["data"]["status"] == "paid"
    assert outputs[-1]["data"]["final"] is True


def test_orders_wait_returns_one_when_failed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_client = _mock_client_with_orders([
        _make_order_response(status="failed", paid_at=None)
    ])
    fake_time = MagicMock()
    fake_time.monotonic.side_effect = [0.0, 0.0, 0.0]
    fake_time.sleep = MagicMock()

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch("cli.commands.payments.handlers.time", fake_time),
    ):
        rc = handle_payments_orders_wait(_make_args(timeout=120, interval=5))

    assert rc == 1
    payload = json.loads(capsys.readouterr().out.strip().split("\n\n")[-1])
    assert payload["data"]["status"] == "failed"


def test_orders_wait_returns_two_on_timeout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_client = _mock_client_with_orders([
        _make_order_response(status="pending", paid_at=None)
    ])
    fake_time = MagicMock()
    fake_time.monotonic.side_effect = [0.0, 2.0, 2.0]
    fake_time.sleep = MagicMock()

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch("cli.commands.payments.handlers.time", fake_time),
    ):
        rc = handle_payments_orders_wait(_make_args(timeout=1, interval=1))

    assert rc == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["data"]["code"] == "order_timeout"


def test_orders_wait_returns_plain_text_timeout_without_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_client = _mock_client_with_orders([
        _make_order_response(status="pending", paid_at=None)
    ])
    fake_time = MagicMock()
    fake_time.monotonic.side_effect = [0.0, 2.0, 2.0]
    fake_time.sleep = MagicMock()

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=False),
        ),
        patch("cli.commands.payments.handlers.time", fake_time),
    ):
        rc = handle_payments_orders_wait(
            _make_args(timeout=1, interval=1, json_output=False)
        )

    assert rc == 2
    captured = capsys.readouterr()
    assert captured.out.strip() == (
        "Order 880e8400-e29b-41d4-a716-446655440003: "
        "status=pending (elapsed 2s)"
    )
    assert "did not reach terminal state within 1s" in captured.err
    assert '"kind": "logion.error"' not in captured.err


def test_orders_wait_respects_timeout_cap_of_six_hundred() -> None:
    mock_client = _mock_client_with_orders([
        _make_order_response(status="pending", paid_at=None)
    ])
    fake_time = MagicMock()
    fake_time.monotonic.side_effect = [0.0, 601.0, 601.0]
    fake_time.sleep = MagicMock()

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch("cli.commands.payments.handlers.time", fake_time),
        patch(
            "cli.commands.payments.handlers.emit_error_json"
        ) as mock_emit_error,
    ):
        rc = handle_payments_orders_wait(_make_args(timeout=9999, interval=1))

    assert rc == 2
    mock_emit_error.assert_called_once()
    assert "within 600s" in mock_emit_error.call_args[0][1]


def test_orders_wait_polls_at_configured_interval() -> None:
    pending = _make_order_response(status="pending", paid_at=None)
    paid = _make_order_response(status="paid")
    mock_client = _mock_client_with_orders([pending, paid])
    fake_time = MagicMock()
    fake_time.monotonic.side_effect = [0.0, 0.0, 3.0, 3.0, 3.0]
    fake_time.sleep = MagicMock()

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch("cli.commands.payments.handlers.time", fake_time),
    ):
        rc = handle_payments_orders_wait(_make_args(timeout=120, interval=3))

    assert rc == 0
    fake_time.sleep.assert_called_once_with(3)

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


def _make_order_response(**overrides: object) -> OrderResponse:
    """Create an OrderResponse with sensible defaults."""
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
    }
    defaults.update(overrides)
    return OrderResponse(**defaults)  # type: ignore[arg-type]


def _make_args(**overrides: object) -> argparse.Namespace:
    """Build a default args namespace for testing."""
    defaults: dict[str, object] = {
        "order_id": "880e8400-e29b-41d4-a716-446655440003",
        "json_output": True,
        "api_key": None,
        "base_url": None,
        "timeout": None,
        "max_retries": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _default_config(**overrides: object) -> CliConfig:
    """Build a default CliConfig for testing."""
    defaults: dict[str, object] = {
        "api_key": None,
        "base_url": "https://api.logion.dev",
        "json_output": True,
        "timeout": None,
        "max_retries": None,
    }
    defaults.update(overrides)
    return CliConfig(**defaults)  # type: ignore[arg-type]


def _mock_client_with_order(
    mock_result: MagicMock,
) -> MagicMock:
    """Build a mock client whose get_order returns *mock_result*."""
    mock_payments = MagicMock()
    mock_payments.get_order = MagicMock(return_value=mock_result)
    mock_v1 = MagicMock()
    mock_v1.payments = mock_payments
    mock_client = MagicMock()
    mock_client.v1 = mock_v1
    mock_client.close = MagicMock()
    return mock_client


# ── orders get envelope tests ─────────────────────────────────


def test_orders_get_json_envelope_v1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When --json is active, orders get emits a v1 envelope."""
    order = _make_order_response()
    mock_result = MagicMock()
    mock_result.model_dump = MagicMock(
        return_value=order.model_dump(mode="json")
    )
    mock_client = _mock_client_with_order(mock_result)
    args = _make_args(json_output=True)

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
        rc = handle_orders_get(args)

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.payments.orders.get"
    assert "id" in payload["data"]
    assert "status" in payload["data"]


def test_orders_get_includes_status_field(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The data section of orders get envelope has a status field."""
    order = _make_order_response(status="paid")
    mock_result = MagicMock()
    mock_result.model_dump = MagicMock(
        return_value=order.model_dump(mode="json")
    )
    mock_client = _mock_client_with_order(mock_result)
    args = _make_args(json_output=True)

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
        rc = handle_orders_get(args)

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["status"] == "paid"


def test_orders_get_unsafe_order_id_returns_error() -> None:
    """orders get with an invalid UUID returns exit code 2."""
    args = _make_args(order_id="not-a-uuid")
    rc = handle_orders_get(args)
    assert rc == 2


# ── orders wait tests ─────────────────────────────────────────


def test_orders_wait_returns_zero_when_paid_immediately(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Orders wait returns 0 when the order is paid immediately."""
    mock_result = MagicMock()
    mock_result.status = "paid"
    mock_client = _mock_client_with_order(mock_result)
    args = _make_args(interval=5, timeout=120)

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch(
            "cli.commands.payments.handlers.time.sleep",
        ),
    ):
        rc = handle_payments_orders_wait(args)

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.payments.orders.wait"
    assert payload["data"]["status"] == "paid"


def test_orders_wait_returns_one_when_failed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Orders wait returns 1 when the order status is failed."""
    mock_result = MagicMock()
    mock_result.status = "failed"
    mock_client = _mock_client_with_order(mock_result)
    args = _make_args(interval=5, timeout=120)

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch(
            "cli.commands.payments.handlers.time.sleep",
        ),
    ):
        rc = handle_payments_orders_wait(args)

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["status"] == "failed"


def test_orders_wait_returns_two_on_timeout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Orders wait returns 2 when order doesn't reach terminal state."""
    mock_result = MagicMock()
    mock_result.status = "pending"
    mock_client = _mock_client_with_order(mock_result)
    args = _make_args(interval=1, timeout=1)

    monotonic_calls = [0]

    def fake_monotonic() -> float:
        monotonic_calls[0] += 1
        if monotonic_calls[0] == 1:
            return 0.0
        return 2.0  # elapsed > timeout (1s)

    mock_time = MagicMock()
    mock_time.monotonic = fake_monotonic
    mock_time.sleep = MagicMock()

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch(
            "cli.commands.payments.handlers.time",
            mock_time,
        ),
    ):
        rc = handle_payments_orders_wait(args)

    assert rc == 2
    error_payload = json.loads(capsys.readouterr().err)
    assert error_payload["data"]["code"] == "order_timeout"


def test_orders_wait_caps_timeout_at_six_hundred() -> None:
    """Orders wait caps timeout at 600s even with a larger value."""
    mock_result_pending = MagicMock()
    mock_result_pending.status = "pending"

    mock_payments = MagicMock()
    call_count = [0]

    def get_order_pending(**_kwargs: object) -> MagicMock:
        call_count[0] += 1
        return mock_result_pending

    mock_payments.get_order = get_order_pending
    mock_v1 = MagicMock()
    mock_v1.payments = mock_payments
    mock_client = MagicMock()
    mock_client.v1 = mock_v1
    mock_client.close = MagicMock()

    args = _make_args(timeout=9999, interval=1)

    monotonic_calls = [0]

    def fake_monotonic() -> float:
        monotonic_calls[0] += 1
        if monotonic_calls[0] == 1:
            return 0.0
        return 601.0

    mock_time = MagicMock()
    mock_time.monotonic = fake_monotonic
    mock_time.sleep = MagicMock()

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch(
            "cli.commands.payments.handlers.time",
            mock_time,
        ),
        patch(
            "cli.commands.payments.handlers.emit_error_json",
        ) as mock_emit_error,
    ):
        rc = handle_payments_orders_wait(args)

    assert rc == 2
    mock_emit_error.assert_called_once()
    call_args = mock_emit_error.call_args
    assert (
        call_args[0][1] == "Order 880e8400-e29b-41d4-a716-446655440003 "
        "did not reach terminal state within 600s"
    )


def test_orders_wait_respects_interval() -> None:
    """Orders wait calls time.sleep with the specified interval."""
    call_count = [0]

    def get_order_polling(**_kwargs: object) -> MagicMock:
        call_count[0] += 1
        mock = MagicMock()
        if call_count[0] < 3:
            mock.status = "pending"
        else:
            mock.status = "paid"
        return mock

    mock_payments = MagicMock()
    mock_payments.get_order = get_order_polling
    mock_v1 = MagicMock()
    mock_v1.payments = mock_payments
    mock_client = MagicMock()
    mock_client.v1 = mock_v1
    mock_client.close = MagicMock()

    args = _make_args(interval=3, timeout=120)

    monotonic_calls = [0]

    def fake_monotonic() -> float:
        monotonic_calls[0] += 1
        return float(monotonic_calls[0])

    mock_time = MagicMock()
    mock_time.monotonic = fake_monotonic
    mock_time.sleep = MagicMock()

    with (
        patch(
            "cli.commands.payments.handlers.make_client",
            return_value=mock_client,
        ),
        patch(
            "cli.commands.payments.handlers.resolve_config_from_args",
            return_value=_default_config(json_output=True),
        ),
        patch(
            "cli.commands.payments.handlers.time",
            mock_time,
        ),
    ):
        rc = handle_payments_orders_wait(args)

    assert rc == 0
    for call in mock_time.sleep.call_args_list:
        assert call[0][0] == 3

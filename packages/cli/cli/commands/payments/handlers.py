# SPDX-License-Identifier: MIT
"""Handlers for payments commands."""

from __future__ import annotations

import argparse
import sys
import time

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import emit_error_json, handle_error
from cli._output import emit, emit_json, to_data
from logion.v1._types.generated.v1 import CourseCheckoutResponse

from ._orders_helpers import (
    TERMINAL_STATUSES,
    emit_wait_result,
    order_to_payload,
    timeout_payload,
    validate_uuid_arg,
)


def _render_checkout(
    payload: CourseCheckoutResponse,
    *,
    json_output: bool,
) -> None:
    """Render a checkout response, hiding Stripe URL for free flows."""
    if json_output:
        sys.stdout.write(payload.model_dump_json(indent=2))
        sys.stdout.write("\n")
        return
    lines = [
        f"order_id: {payload.order_id}",
        f"order_reference: {payload.order_reference}",
        f"purchase_flow: {payload.purchase_flow}",
        f"checkout_required: {str(payload.checkout_required).lower()}",
        f"order_status: {payload.order_status}",
        f"entitlement_granted: {str(payload.entitlement_granted).lower()}",
    ]
    if payload.checkout_url:
        lines.append(f"checkout_url: {payload.checkout_url}")
    sys.stdout.write("\n".join(lines))
    sys.stdout.write("\n")


def handle_seller_readiness(args: argparse.Namespace) -> int:
    """Execute the payments seller-readiness command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.get_seller_readiness()
        if config.json_output:
            emit_json("logion.payments.seller-readiness", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_onboarding_link(args: argparse.Namespace) -> int:
    """Execute the payments onboarding-link command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.create_onboarding_link()
        if config.json_output:
            emit_json("logion.payments.onboarding-link", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_checkout(args: argparse.Namespace) -> int:
    """Execute the payments checkout command."""
    bad_id = validate_uuid_arg(args, args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.create_checkout(
            course_id=args.course_id,
            price_cents=args.price_cents,
        )
        _render_checkout(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_orders_get(args: argparse.Namespace) -> int:
    """Execute the payments orders get command."""
    bad_id = validate_uuid_arg(args, args.order_id, "ORDER_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.get_order(order_id=args.order_id)
    except Exception as exc:
        return handle_error(exc)
    else:
        payload = order_to_payload(result)
        if config.json_output:
            emit_json("logion.payments.orders.get", payload)
        else:
            emit(payload, json_output=False)
        return 0
    finally:
        client.close()


def handle_payments_orders_wait(
    args: argparse.Namespace,
) -> int:
    """Poll until an order reaches a terminal state."""
    bad_id = validate_uuid_arg(args, args.order_id, "ORDER_ID")
    if bad_id is not None:
        return bad_id

    timeout = min(max(args.timeout, 1), 600)
    interval = max(args.interval, 1)

    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        last_status: str | None = None
        last_payload: dict[str, object] | None = None
        start = time.monotonic()
        while True:
            result = client.v1.payments.get_order(order_id=args.order_id)
            payload = order_to_payload(result)
            status = str(payload.get("status"))
            elapsed = time.monotonic() - start
            if status != last_status:
                emit_wait_result(config, payload, elapsed, final=False)
                last_status = status
            last_payload = payload
            if status in TERMINAL_STATUSES:
                break
            if elapsed >= timeout:
                break
            time.sleep(interval)
    except Exception as exc:
        return handle_error(exc)
    finally:
        client.close()

    elapsed = time.monotonic() - start
    payload = last_payload or timeout_payload(args.order_id)

    if payload.get("status") == "paid":
        emit_wait_result(config, payload, elapsed, final=True)
        return 0

    if payload.get("status") in {"failed", "refunded"}:
        emit_wait_result(config, payload, elapsed, final=True)
        return 1

    msg = (
        f"Order {args.order_id} did not reach terminal state within {timeout}s"
    )
    if config.json_output:
        emit_error_json("order_timeout", msg, 2)
    else:
        sys.stderr.write(f"ERROR: {msg}\n")
    return 2

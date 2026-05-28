"""Handlers for payments commands."""

from __future__ import annotations

import argparse
import sys
import time

from cli._config import CliConfig, resolve_config_from_args
from cli._context import make_client
from cli._errors import emit_error_json, handle_error, validate_uuid_id
from cli._output import emit, emit_json
from logion.v1._types.generated.v1 import CourseCheckoutResponse

TERMINAL_STATUSES = frozenset({"paid", "failed", "refunded"})


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
        emit(result, json_output=config.json_output)
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
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_checkout(args: argparse.Namespace) -> int:
    """Execute the payments checkout command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
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
    bad_id = validate_uuid_id(args.order_id, "ORDER_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.get_order(order_id=args.order_id)
    except Exception as exc:
        return handle_error(exc)
    else:
        if config.json_output:
            data = (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else dict(result)
            )
            emit_json("logion.payments.orders.get", data)
        else:
            emit(result, json_output=False)
        return 0
    finally:
        client.close()


def _emit_wait_result(
    args: argparse.Namespace,
    config: CliConfig,
    status: str,
    elapsed: float,
) -> None:
    """Emit the wait result in the appropriate format."""
    summary = (
        f"Order {args.order_id}: status={status} (settled in {int(elapsed)}s)"
    )
    if config.json_output:
        emit_json(
            "logion.payments.orders.wait",
            {
                "order_id": args.order_id,
                "status": status,
                "elapsed_seconds": round(elapsed, 2),
            },
        )
    else:
        sys.stdout.write(summary)
        sys.stdout.write("\n")


def handle_payments_orders_wait(
    args: argparse.Namespace,
) -> int:
    """Poll until an order reaches a terminal state."""
    bad_id = validate_uuid_id(args.order_id, "ORDER_ID")
    if bad_id is not None:
        return bad_id

    timeout = min(args.timeout, 600)
    interval = max(args.interval, 1)

    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        status = ""
        start = time.monotonic()
        while True:
            result = client.v1.payments.get_order(
                order_id=args.order_id,
            )
            status = result.status
            if status in TERMINAL_STATUSES:
                break
            if time.monotonic() - start >= timeout:
                break
            time.sleep(interval)
    except Exception as exc:
        return handle_error(exc)
    finally:
        client.close()

    elapsed = time.monotonic() - start

    if status == "paid":
        _emit_wait_result(args, config, status, elapsed)
        return 0

    if status in {"failed", "refunded"}:
        _emit_wait_result(args, config, status, elapsed)
        return 1

    # Timeout: terminal state not reached
    msg = (
        f"Order {args.order_id} did not reach terminal state within {timeout}s"
    )
    emit_error_json("order_timeout", msg, 2)
    return 2

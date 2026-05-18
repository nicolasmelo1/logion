"""Handlers for payments commands."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, validate_uuid_id
from cli._output import emit
from logion.v1._types.generated.v1 import CourseCheckoutResponse


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
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

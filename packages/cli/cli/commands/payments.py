"""Payments commands — checkout, orders, and seller onboarding."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import (
    handle_error,
    validate_uuid_id,
)
from cli._options import COMMON_PARSER
from cli._output import emit


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``payments`` subcommand group."""
    parser = subparsers.add_parser(
        "payments",
        help="Manage payments and seller onboarding",
    )
    sub = parser.add_subparsers(
        dest="payments_command",
        required=True,
    )

    # ── seller-readiness ─────────────────────────────────────────
    sr = sub.add_parser(
        "seller-readiness",
        help="Check seller readiness status",
        parents=[COMMON_PARSER],
    )
    sr.set_defaults(handler=handle_seller_readiness)

    # ── onboarding-link ──────────────────────────────────────────
    ol = sub.add_parser(
        "onboarding-link",
        help="Create a Stripe onboarding link",
        parents=[COMMON_PARSER],
    )
    ol.set_defaults(handler=handle_onboarding_link)

    # ── checkout ─────────────────────────────────────────────────
    co = sub.add_parser(
        "checkout",
        help="Create a checkout session for a course",
        parents=[COMMON_PARSER],
    )
    co.add_argument("course_id")
    co.set_defaults(handler=handle_checkout)

    # ── orders get ────────────────────────────────────────────────
    orders = sub.add_parser(
        "orders",
        help="Manage orders",
    )
    orders_sub = orders.add_subparsers(
        dest="payments_orders_command",
        required=True,
    )
    og = orders_sub.add_parser(
        "get",
        help="Get order details",
        parents=[COMMON_PARSER],
    )
    og.add_argument("order_id")
    og.set_defaults(handler=handle_orders_get)


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
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.create_checkout(course_id=args.course_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_orders_get(args: argparse.Namespace) -> int:
    """Execute the payments orders get command."""
    bad_id = validate_uuid_id(args.order_id, "order_id")
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

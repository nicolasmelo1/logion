"""Parser registration for payments commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import (
    handle_checkout,
    handle_onboarding_link,
    handle_orders_get,
    handle_seller_readiness,
)


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

    seller_readiness = sub.add_parser(
        "seller-readiness",
        help="Check seller readiness status",
        parents=[COMMON_PARSER],
    )
    seller_readiness.set_defaults(handler=handle_seller_readiness)

    onboarding_link = sub.add_parser(
        "onboarding-link",
        help="Create a Stripe onboarding link",
        parents=[COMMON_PARSER],
    )
    onboarding_link.set_defaults(handler=handle_onboarding_link)

    checkout = sub.add_parser(
        "checkout",
        help="Create a checkout session for a course",
        parents=[COMMON_PARSER],
    )
    checkout.add_argument("course_id", metavar="COURSE_ID")
    checkout.set_defaults(handler=handle_checkout)

    orders = sub.add_parser("orders", help="Manage orders")
    orders_sub = orders.add_subparsers(
        dest="payments_orders_command",
        required=True,
    )
    orders_get = orders_sub.add_parser(
        "get",
        help="Get order details",
        parents=[COMMON_PARSER],
    )
    orders_get.add_argument("order_id", metavar="ORDER_ID")
    orders_get.set_defaults(handler=handle_orders_get)

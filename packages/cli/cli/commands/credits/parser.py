# SPDX-License-Identifier: MIT
"""Parser registration for credits commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import (
    handle_credits_balance,
    handle_credits_ledger,
    handle_credits_top_up,
    handle_credits_top_ups_get,
    handle_credits_top_ups_wait,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``credits`` subcommand group."""
    parser = subparsers.add_parser(
        "credits",
        help="Manage credit balance, top-ups, and ledger",
    )
    sub = parser.add_subparsers(
        dest="credits_command",
        required=True,
    )

    # credits balance
    balance = sub.add_parser(
        "balance",
        help="Show current credit balance",
        parents=[COMMON_PARSER],
    )
    balance.set_defaults(handler=handle_credits_balance)

    # credits top-up
    top_up = sub.add_parser(
        "top-up",
        help="Create a credit top-up checkout session",
        parents=[COMMON_PARSER],
    )
    top_up.add_argument(
        "--amount",
        dest="amount_cents",
        required=True,
        type=int,
        help="Amount in USD cents for the credit top-up.",
    )
    top_up.add_argument(
        "--currency",
        dest="currency",
        default="usd",
        type=lambda v: v.lower().strip(),
        help=(
            "Charge currency (ISO 4217, case-insensitive). "
            "Default: usd. When not usd, the charge is converted "
            "at the current exchange rate; credits are always "
            "granted in USD."
        ),
    )
    top_up.add_argument(
        "--yes",
        action="store_true",
        help="Confirm creating a Stripe Checkout session for this top-up.",
    )
    top_up.add_argument(
        "--wait",
        action="store_true",
        default=False,
        help="Poll until the top-up reaches a terminal state.",
    )
    top_up.add_argument(
        "--wait-timeout",
        dest="wait_timeout",
        type=int,
        default=300,
        help="Max seconds to poll (capped at 600).",
    )
    top_up.set_defaults(handler=handle_credits_top_up)

    # credits top-ups (nested sub-group)
    top_ups = sub.add_parser("top-ups", help="Query credit top-ups")
    top_ups_sub = top_ups.add_subparsers(
        dest="credits_top_ups_command",
        required=True,
    )

    # credits top-ups get
    top_ups_get = top_ups_sub.add_parser(
        "get",
        help="Get a credit top-up by ID",
        parents=[COMMON_PARSER],
    )
    top_ups_get.add_argument("top_up_id", metavar="TOP_UP_ID")
    top_ups_get.set_defaults(handler=handle_credits_top_ups_get)

    # credits top-ups wait
    top_ups_wait = top_ups_sub.add_parser(
        "wait",
        help="Poll until a top-up reaches a terminal state",
        parents=[COMMON_PARSER],
    )
    top_ups_wait.add_argument("top_up_id", metavar="TOP_UP_ID")
    top_ups_wait.add_argument(
        "--wait-timeout",
        dest="wait_timeout",
        type=int,
        default=300,
        help="Max seconds to poll (capped at 600).",
    )
    top_ups_wait.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Seconds between polls.",
    )
    top_ups_wait.set_defaults(handler=handle_credits_top_ups_wait)

    # credits ledger
    ledger = sub.add_parser(
        "ledger",
        help="List credit ledger entries",
        parents=[COMMON_PARSER],
    )
    ledger.set_defaults(handler=handle_credits_ledger)

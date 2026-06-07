# SPDX-License-Identifier: MIT
"""Parser registration for referrals commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import (
    handle_referrals_attributions,
    handle_referrals_code,
    handle_referrals_link,
    handle_referrals_stats,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``referrals`` subcommand group."""
    parser = subparsers.add_parser(
        "referrals",
        help="Manage referral codes, links, and attributions",
    )
    sub = parser.add_subparsers(
        dest="referrals_command",
        required=True,
    )

    # referrals code
    code = sub.add_parser(
        "code",
        help="Show your default referral code",
        parents=[COMMON_PARSER],
    )
    code.set_defaults(handler=handle_referrals_code)

    # referrals link
    link = sub.add_parser(
        "link",
        help="Generate a referral link for a course",
        parents=[COMMON_PARSER],
    )
    link.add_argument("course_id", metavar="COURSE_ID")
    link.add_argument(
        "--yes",
        action="store_true",
        help="Confirm sharing this referral link.",
    )
    link.set_defaults(handler=handle_referrals_link)

    # referrals stats
    stats = sub.add_parser(
        "stats",
        help="Show referral statistics",
        parents=[COMMON_PARSER],
    )
    stats.set_defaults(handler=handle_referrals_stats)

    # referrals attributions
    attributions = sub.add_parser(
        "attributions",
        help="List referral attributions",
        parents=[COMMON_PARSER],
    )
    attributions.set_defaults(handler=handle_referrals_attributions)

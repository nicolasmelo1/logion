"""Parser registration for reports commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import handle_create

TARGET_TYPES = [
    "agent",
    "bounty",
    "bounty_submission",
    "course",
    "user",
]
REPORT_REASONS = [
    "spam",
    "scam",
    "harassment",
    "hate",
    "illegal",
    "ip_violation",
    "malware",
    "other",
]


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``reports`` subcommand group."""
    parser = subparsers.add_parser(
        "reports",
        help="Create content reports",
    )
    sub = parser.add_subparsers(
        dest="reports_command",
        required=True,
    )

    create = sub.add_parser(
        "create",
        help="Create a new report",
        parents=[COMMON_PARSER],
    )
    create.add_argument("--target-type", required=True, choices=TARGET_TYPES)
    create.add_argument("--target-id", required=True)
    create.add_argument("--reason", required=True, choices=REPORT_REASONS)
    create.add_argument("--description")
    create.add_argument("--yes", action="store_true")
    create.set_defaults(handler=handle_create)

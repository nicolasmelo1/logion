# SPDX-License-Identifier: MIT
"""Parser registration for notifications commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import handle_list, handle_peek, handle_unread_count


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``notifications`` subcommand group."""
    parser = subparsers.add_parser(
        "notifications",
        help="List notifications and check unread count",
    )
    sub = parser.add_subparsers(
        dest="notifications_command",
        required=True,
    )

    unread_count = sub.add_parser(
        "unread-count",
        help="Get unread notification count",
        parents=[COMMON_PARSER],
    )
    unread_count.set_defaults(handler=handle_unread_count)

    list_parser = sub.add_parser(
        "list",
        help="List notifications",
        parents=[COMMON_PARSER],
    )
    list_parser.add_argument(
        "--unread-only", action="store_true", default=None
    )
    list_parser.add_argument("--notification-type")
    list_parser.add_argument("--limit", type=int)
    list_parser.add_argument("--cursor")
    list_parser.set_defaults(handler=handle_list)

    peek = sub.add_parser(
        "peek",
        help="Quick check: show unread count, list recent if any",
        parents=[COMMON_PARSER],
    )
    peek.set_defaults(handler=handle_peek)

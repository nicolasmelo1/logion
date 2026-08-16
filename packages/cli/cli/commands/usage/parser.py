# SPDX-License-Identifier: MIT
"""Parser registration for usage observation commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import (
    handle_usage_dismiss,
    handle_usage_observe,
    handle_usage_pending,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``usage`` subcommand group."""
    parser = subparsers.add_parser(
        "usage",
        help="Observe and manage resource usage events",
    )
    sub = parser.add_subparsers(
        dest="usage_command",
        required=True,
    )

    # usage pending
    pending = sub.add_parser(
        "pending",
        help="List pending usage observations from the local spool",
        parents=[COMMON_PARSER],
    )
    pending.add_argument(
        "--since",
        dest="since",
        default="24h",
        help="Only show observations newer than this window (e.g. 24h, 1h).",
    )
    pending.set_defaults(handler=handle_usage_pending)

    # usage observe
    observe = sub.add_parser(
        "observe",
        help="Read an observation from stdin and write it to the local spool",
        parents=[COMMON_PARSER],
    )
    observe.add_argument(
        "--harness",
        required=True,
        help="Harness name (e.g. codex, claude-code).",
    )
    observe.add_argument(
        "--stdin",
        action="store_true",
        default=True,
        help="Read observation data from stdin.",
    )
    observe.set_defaults(handler=handle_usage_observe)

    # usage dismiss
    dismiss = sub.add_parser(
        "dismiss",
        help="Remove observations by group id from the local spool",
        parents=[COMMON_PARSER],
    )
    dismiss.add_argument(
        "observation_group_id",
        metavar="OBSERVATION_GROUP_ID",
    )
    dismiss.set_defaults(handler=handle_usage_dismiss)

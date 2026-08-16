# SPDX-License-Identifier: MIT
"""Parser registration for integration management commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import (
    handle_integrations_detect,
    handle_integrations_disable,
    handle_integrations_enable,
    handle_integrations_status,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``integrations`` subcommand group."""
    parser = subparsers.add_parser(
        "integrations",
        help="Detect and manage supported harness integrations",
    )
    sub = parser.add_subparsers(
        dest="integrations_command",
        required=True,
    )

    # integrations detect
    detect = sub.add_parser(
        "detect",
        help="Detect supported harnesses installed on this machine",
        parents=[COMMON_PARSER],
    )
    detect.set_defaults(handler=handle_integrations_detect)

    # integrations enable
    enable = sub.add_parser(
        "enable",
        help="Enable observation integration for a harness",
        parents=[COMMON_PARSER],
    )
    enable.add_argument("harness", metavar="HARNESS")
    enable.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
    )
    enable.add_argument(
        "--mode",
        choices=["prompt", "auto", "local-only"],
        default="prompt",
    )
    enable.set_defaults(handler=handle_integrations_enable)

    # integrations disable
    disable = sub.add_parser(
        "disable",
        help="Disable observation integration for a harness",
        parents=[COMMON_PARSER],
    )
    disable.add_argument("harness", metavar="HARNESS")
    disable.set_defaults(handler=handle_integrations_disable)

    # integrations status
    status = sub.add_parser(
        "status",
        help="Show integration status for all harnesses",
        parents=[COMMON_PARSER],
    )
    status.set_defaults(handler=handle_integrations_status)

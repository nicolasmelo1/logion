# SPDX-License-Identifier: MIT
"""Parser registration for indexed listings commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import handle_indexed_get


def register(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register the ``indexed`` subcommand group."""
    parser = subparsers.add_parser(
        "indexed",
        help="Read-only discovery commands for indexed external listings",
    )
    sub = parser.add_subparsers(
        dest="indexed_command",
        required=True,
    )

    get = sub.add_parser(
        "get",
        help="Get detail for an indexed external listing",
        parents=[COMMON_PARSER],
    )
    get.add_argument("listing_id")
    get.set_defaults(handler=handle_indexed_get)

    return parser

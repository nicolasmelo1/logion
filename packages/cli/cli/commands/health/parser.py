"""Parser registration for the health command."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import handle_health


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``health`` subcommand."""
    parser = subparsers.add_parser(
        "health",
        help="Check API health",
        parents=[COMMON_PARSER],
    )
    parser.set_defaults(handler=handle_health)

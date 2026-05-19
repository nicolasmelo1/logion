"""Parser registration for course capability commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli._options import COMMON_PARSER

from .capabilities import (
    handle_courses_capabilities_print,
    handle_courses_capabilities_validate,
)
from .parser_sections import CMD_HELP


def register_capabilities(subparsers: argparse._SubParsersAction) -> None:
    """Register course capability manifest subcommands."""
    capabilities = subparsers.add_parser(
        "capabilities",
        help=CMD_HELP["capabilities"],
    )
    capabilities_sub = capabilities.add_subparsers(
        dest="courses_capabilities_command",
        required=True,
    )

    validate = capabilities_sub.add_parser(
        "validate",
        help="Validate a local capability manifest",
        parents=[COMMON_PARSER],
    )
    validate.add_argument(
        "--bundle-dir",
        type=Path,
        required=True,
        help="Path to the course bundle directory",
    )
    validate.set_defaults(handler=handle_courses_capabilities_validate)

    print_cmd = capabilities_sub.add_parser(
        "print",
        help="Print the normalised capability manifest as JSON",
        parents=[COMMON_PARSER],
    )
    print_cmd.add_argument(
        "--bundle-dir",
        type=Path,
        required=True,
        help="Path to the course bundle directory",
    )
    print_cmd.set_defaults(handler=handle_courses_capabilities_print)

# SPDX-License-Identifier: MIT
"""Parser registration for course capability commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli._options import COMMON_PARSER

from .capabilities import (
    handle_courses_capabilities_print,
    handle_courses_capabilities_scaffold,
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

    scaffold = capabilities_sub.add_parser(
        "scaffold",
        help="Write a commented course/capabilities.yaml scaffold",
        parents=[COMMON_PARSER],
    )
    scaffold.add_argument(
        "--bundle-dir",
        type=Path,
        default=None,
        help=(
            "Course bundle directory.  If omitted the scaffold is "
            "printed to stdout."
        ),
    )
    scaffold.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing course/capabilities.yaml",
    )
    scaffold.add_argument(
        "--license-template",
        choices=["mit", "apache-2.0", "logion-standard-course-v1"],
        default=None,
        help=(
            "Write bundle-dir/LICENSE from the selected template. "
            "When omitted, scaffold writes MIT by default."
        ),
    )
    scaffold.add_argument(
        "--from-skill",
        type=Path,
        default=None,
        metavar="SKILL_MD_PATH",
        help=(
            "Seed the scaffold from the metadata.logion capability "
            "manifest in the given SKILL.md instead of emitting the "
            "generic template."
        ),
    )
    scaffold.set_defaults(handler=handle_courses_capabilities_scaffold)

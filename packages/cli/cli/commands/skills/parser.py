# SPDX-License-Identifier: MIT
"""Parser registration for skills commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli._options import COMMON_PARSER

from ._search_handler import handle_skills_search
from .handlers import (
    handle_skills_inspect,
    handle_skills_install,
    handle_skills_installed,
    handle_skills_update,
    handle_skills_updates,
    handle_skills_verify,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``skills`` subcommand group."""
    parser = subparsers.add_parser(
        "skills",
        help="Manage locally installed marketplace skills",
    )
    sub = parser.add_subparsers(
        dest="skills_command",
        required=True,
    )

    install = sub.add_parser(
        "install",
        help="Install a skill bundle from a local source directory",
        parents=[COMMON_PARSER],
    )
    install.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the skill bundle source directory",
    )
    install.add_argument("--course-id", required=True)
    install.add_argument("--version-id", required=True)
    install.add_argument("--title", default=None)
    install.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Override LOGION_HOME for the install target",
    )
    install.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be installed without writing files",
    )
    install.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing install with different content",
    )
    install.add_argument(
        "--install-source",
        default="manual",
        choices=["manual", "logion-marketplace"],
        help="Provenance of the install (default: manual)",
    )
    install.add_argument(
        "--symlink-dir",
        default=None,
        help=(
            "Copy the installed skill into this agent skill directory "
            "(e.g. ~/.claude/skills). Skip the interactive prompt."
        ),
    )
    install.add_argument(
        "--no-symlink",
        action="store_true",
        help=(
            "Skip the agent skill-copy prompt entirely "
            "(canonical install only)"
        ),
    )
    install.set_defaults(handler=handle_skills_install)

    installed = sub.add_parser(
        "installed",
        help="List installed skills",
        parents=[COMMON_PARSER],
    )
    installed.add_argument("--target", type=Path, default=None)
    installed.set_defaults(handler=handle_skills_installed)

    inspect = sub.add_parser(
        "inspect",
        help="Show the manifest for an installed skill",
        parents=[COMMON_PARSER],
    )
    inspect.add_argument("course_id", metavar="COURSE_ID")
    inspect.add_argument("--version-id", default=None)
    inspect.add_argument("--verbose", action="store_true", default=False)
    inspect.add_argument("--target", type=Path, default=None)
    inspect.set_defaults(handler=handle_skills_inspect)

    updates = sub.add_parser(
        "updates",
        help="Report integrity and update status for installed skills",
        parents=[COMMON_PARSER],
    )
    updates.add_argument("--target", type=Path, default=None)
    updates.set_defaults(handler=handle_skills_updates)

    update = sub.add_parser(
        "update",
        help="Apply an update to an installed skill",
        parents=[COMMON_PARSER],
    )
    update.add_argument("course_id", metavar="COURSE_ID")
    update.add_argument("--version-id", required=True)
    update.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the new skill bundle source directory",
    )
    update.add_argument("--title", default=None)
    update.add_argument("--target", type=Path, default=None)
    update.add_argument(
        "--force",
        action="store_true",
        help="Overwrite a locally modified installation",
    )
    update.set_defaults(handler=handle_skills_update)

    verify = sub.add_parser(
        "verify",
        help="Re-state locally stored entitlement status for installed skills",
        parents=[COMMON_PARSER],
    )
    verify.add_argument("course_id", nargs="?", default=None)
    verify.add_argument("--target", type=Path, default=None)
    verify.set_defaults(handler=handle_skills_verify)

    search = sub.add_parser(
        "search",
        help=(
            "Search marketplace listings"
            " with installed/entitlement annotations"
        ),
        parents=[COMMON_PARSER],
    )
    search.add_argument("query", metavar="QUERY")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--verbose", action="store_true", default=False)
    search.add_argument("--target", type=Path, default=None)
    search.set_defaults(handler=handle_skills_search)

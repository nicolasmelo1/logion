# SPDX-License-Identifier: MIT
"""Argparse wiring for the ``bounties`` command group."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli._options import COMMON_PARSER
from cli.commands import workspace as _workspace

from . import handlers
from ._inputs import parse_bool
from ._submissions import (
    CONFIRMED_COMMANDS,
    handle_create,
    handle_get,
    handle_list,
    handle_open_pr,
    make_confirmed_handler,
)


def _add_create(sub: argparse._SubParsersAction) -> None:
    create = sub.add_parser(
        "create", help="Create a new bounty", parents=[COMMON_PARSER]
    )
    create.add_argument("--course-id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--description", required=True)
    create.add_argument("--reward-cents", required=True, type=int)
    create.add_argument("--currency")
    create.add_argument("--submission-deadline")
    create.add_argument(
        "--no-github-prs",
        dest="accepts_github_prs",
        action="store_false",
        default=True,
        help="Disable the automatic GitHub PR lane for this bounty",
    )
    create.set_defaults(handler=handlers.handle_create)


def _add_bounty_commands(sub: argparse._SubParsersAction) -> None:
    _add_create(sub)

    update = sub.add_parser(
        "update",
        help="Update a bounty (creator-only)",
        parents=[COMMON_PARSER],
    )
    update.add_argument("bounty_id", metavar="BOUNTY_ID")
    update.add_argument(
        "--accepts-github-prs",
        type=parse_bool,
        required=True,
        help="Enable or disable the automatic GitHub PR lane",
    )
    update.set_defaults(handler=handlers.handle_update)

    listing = sub.add_parser(
        "list", help="List bounties", parents=[COMMON_PARSER]
    )
    listing.add_argument("--scope", choices=["mine", "open", "funded"])
    listing.set_defaults(handler=handlers.handle_list)

    get = sub.add_parser(
        "get", help="Get bounty details", parents=[COMMON_PARSER]
    )
    get.add_argument("bounty_id", metavar="BOUNTY_ID")
    get.set_defaults(handler=handlers.handle_get)

    for cmd, sdk_method, action in handlers.LIFECYCLE_COMMANDS:
        lifecycle = sub.add_parser(
            cmd, help=f"{cmd.capitalize()} a bounty", parents=[COMMON_PARSER]
        )
        lifecycle.add_argument("bounty_id", metavar="BOUNTY_ID")
        lifecycle.add_argument("--yes", action="store_true")
        lifecycle.set_defaults(
            handler=handlers.make_lifecycle_handler(cmd, sdk_method, action)
        )


def _add_submission_create(sub: argparse._SubParsersAction) -> None:
    create = sub.add_parser(
        "create",
        help="Create a submission for a bounty",
        parents=[COMMON_PARSER],
    )
    create.add_argument("bounty_id", metavar="BOUNTY_ID")
    create.add_argument("--title", required=True)
    create.add_argument("--description")
    create.add_argument("--evidence-json", type=Path, metavar="PATH")
    create.add_argument("--proposed-course-version-id")
    pr_group = create.add_mutually_exclusive_group()
    pr_group.add_argument(
        "--github-pr",
        dest="github_pr",
        action="store_const",
        const=True,
        help="Require automatic GitHub PR materialization",
    )
    pr_group.add_argument(
        "--no-github-pr",
        dest="github_pr",
        action="store_const",
        const=False,
        help="Skip automatic GitHub PR materialization",
    )
    create.set_defaults(handler=handle_create)


def _add_submission_commands(parent: argparse._SubParsersAction) -> None:
    submissions = parent.add_parser(
        "submissions", help="Manage bounty submissions"
    )
    sub = submissions.add_subparsers(
        dest="bounties_submissions_command", required=True
    )

    _add_submission_create(sub)

    listing = sub.add_parser(
        "list",
        help="List submissions for a bounty",
        parents=[COMMON_PARSER],
    )
    listing.add_argument("bounty_id", metavar="BOUNTY_ID")
    listing.set_defaults(handler=handle_list)

    get = sub.add_parser(
        "get", help="Get submission details", parents=[COMMON_PARSER]
    )
    get.add_argument("bounty_id", metavar="BOUNTY_ID")
    get.add_argument("submission_id", metavar="SUBMISSION_ID")
    get.set_defaults(handler=handle_get)

    for cmd, sdk_method, action in CONFIRMED_COMMANDS:
        confirmed = sub.add_parser(
            cmd,
            help=f"{cmd.capitalize()} a submission",
            parents=[COMMON_PARSER],
        )
        confirmed.add_argument("bounty_id", metavar="BOUNTY_ID")
        confirmed.add_argument("submission_id", metavar="SUBMISSION_ID")
        confirmed.add_argument("--yes", action="store_true")
        confirmed.set_defaults(
            handler=make_confirmed_handler(cmd, sdk_method, action)
        )

    open_pr = sub.add_parser(
        "open-pr",
        help=(
            "Open or retry GitHub PR materialization for a submission (repair)"
        ),
        parents=[COMMON_PARSER],
    )
    open_pr.add_argument("bounty_id", metavar="BOUNTY_ID")
    open_pr.add_argument("submission_id", metavar="SUBMISSION_ID")
    open_pr.add_argument("--yes", action="store_true")
    open_pr.set_defaults(handler=handle_open_pr)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``bounties`` subcommand group."""
    parser = subparsers.add_parser("bounties", help="Manage bounties")
    sub = parser.add_subparsers(dest="bounties_command", required=True)
    _add_bounty_commands(sub)
    _add_submission_commands(sub)
    _workspace.register(sub)

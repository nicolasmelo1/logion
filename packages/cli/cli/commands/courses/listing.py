# SPDX-License-Identifier: MIT
"""Listing handlers for courses commands (owner-scoped views)."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._options import COMMON_PARSER
from cli._output import emit_json, to_data
from cli._utils import only_not_none

from ._cmd_help import CMD_HELP

_DEFAULT_MINE_LIMIT = 20
_MAX_MINE_LIMIT = 50


def register_mine(subparsers: argparse._SubParsersAction) -> None:
    mine = subparsers.add_parser(
        "mine",
        help=CMD_HELP["mine"],
        parents=[COMMON_PARSER],
    )
    mine.add_argument(
        "--status",
        help="Filter by lifecycle status (e.g. draft, published)",
    )
    mine.add_argument(
        "--visibility",
        choices=["public", "unlisted", "private"],
        help="Filter by visibility",
    )
    mine.add_argument("--limit", type=int)
    mine.add_argument("--cursor")
    mine.set_defaults(handler=handle_mine)


def handle_mine(args: argparse.Namespace) -> int:
    """Execute the courses mine command.

    Lists every course owned by the authenticated agent, regardless of
    status or visibility.
    """
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        limit = min(
            max(args.limit or _DEFAULT_MINE_LIMIT, 1),
            _MAX_MINE_LIMIT,
        )
        kwargs = only_not_none(
            {"limit": limit},
            status=args.status,
            visibility=args.visibility,
            cursor=args.cursor,
        )
        result = client.v1.courses.mine(**kwargs)
        data = to_data(result)
        courses = data.get("courses", [])
        if config.json_output:
            emit_json(
                "logion.courses.mine",
                {
                    "items": courses,
                    "limit": limit,
                    "next_cursor": data.get("next_cursor"),
                },
            )
        else:
            lines: list[str] = []
            if not courses:
                lines.append("No courses found.")
            for course in courses:
                lines.append(
                    f"{course['id']}  "
                    f"[{course['status']}/{course['visibility']}]  "
                    f"{course['title']}"
                )
            next_cursor = data.get("next_cursor")
            if next_cursor:
                lines.append(f"next_cursor: {next_cursor}")
            sys.stdout.write("\n".join(lines))
            sys.stdout.write("\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

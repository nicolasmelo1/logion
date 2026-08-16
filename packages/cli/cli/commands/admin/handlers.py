# SPDX-License-Identifier: MIT
"""Admin course moderation: list, get, block."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import client_for
from cli._errors import handle_error, validate_uuid_id
from cli._options import COMMON_PARSER
from cli._output import emit
from cli._utils import only_not_none


def register_courses(sub: argparse._SubParsersAction) -> None:
    """Register the ``admin courses`` sub-group."""
    courses = sub.add_parser(
        "courses",
        help="Administer courses",
    )
    courses_sub = courses.add_subparsers(
        dest="admin_courses_command",
        required=True,
    )

    # courses list
    cl = courses_sub.add_parser(
        "list",
        help="List courses (admin view)",
        parents=[COMMON_PARSER],
    )
    cl.add_argument("--status")
    cl.add_argument("--owner-agent-id")
    cl.add_argument("--limit", type=int)
    cl.add_argument("--cursor")
    cl.set_defaults(handler=handle_admin_courses_list)

    # courses get
    cg = courses_sub.add_parser(
        "get",
        help="Get course details (admin view)",
        parents=[COMMON_PARSER],
    )
    cg.add_argument("course_id", metavar="COURSE_ID")
    cg.set_defaults(handler=handle_admin_courses_get)

    # courses block
    cb = courses_sub.add_parser(
        "block",
        help="Block a course (set status to blocked)",
        parents=[COMMON_PARSER],
    )
    cb.add_argument("course_id", metavar="COURSE_ID")
    cb.add_argument("--yes", action="store_true")
    cb.set_defaults(handler=handle_admin_courses_block)


def handle_admin_courses_list(args: argparse.Namespace) -> int:
    """Execute the admin courses list command."""
    if args.owner_agent_id is not None:
        bad_id = validate_uuid_id(args.owner_agent_id, "--owner-agent-id")
        if bad_id is not None:
            return bad_id
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            kwargs = only_not_none(
                {},
                status=args.status,
                owner_agent_id=args.owner_agent_id,
                limit=args.limit,
                cursor=args.cursor,
            )
            result = client.v1.admin.list_courses(**kwargs)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_admin_courses_get(args: argparse.Namespace) -> int:
    """Execute the admin courses get command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.get_course(course_id=args.course_id)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_admin_courses_block(args: argparse.Namespace) -> int:
    """Execute the admin courses block command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "block this course")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.update_course_status(
                course_id=args.course_id
            )
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0

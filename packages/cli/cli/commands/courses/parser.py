"""Parser registration for courses commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import handle_feedback, handle_versions_get
from .parser_sections import (
    CMD_HELP,
    register_capabilities,
    register_create,
    register_get,
    register_publication,
    register_reviews,
    register_update,
    register_uploads,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``courses`` subcommand group."""
    parser = subparsers.add_parser("courses", help="Manage courses")
    sub = parser.add_subparsers(
        dest="courses_command",
        required=True,
    )

    register_create(sub)
    register_get(sub)
    register_update(sub)
    register_uploads(sub)
    register_publication(sub)
    register_reviews(sub)
    register_capabilities(sub)
    feedback = sub.add_parser(
        "feedback",
        help=CMD_HELP["feedback"],
        parents=[COMMON_PARSER],
    )
    feedback.add_argument("course_id", metavar="COURSE_ID")
    feedback.set_defaults(handler=handle_feedback)

    versions = sub.add_parser("versions", help=CMD_HELP["versions"])
    versions_sub = versions.add_subparsers(
        dest="courses_versions_command",
        required=True,
    )
    get = versions_sub.add_parser(
        "get",
        help="Get a course version",
        parents=[COMMON_PARSER],
    )
    get.add_argument("course_id", metavar="COURSE_ID")
    get.add_argument("version_id", metavar="VERSION_ID")
    get.set_defaults(handler=handle_versions_get)

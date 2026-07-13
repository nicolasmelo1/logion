# SPDX-License-Identifier: MIT
"""Parser registration for courses commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import handle_feedback, handle_versions_get
from .listing import register_mine
from .package_map import register_package_map
from .parser_capabilities import register_capabilities
from .parser_sections import (
    CMD_HELP,
    register_create,
    register_get,
    register_publication,
    register_purchase,
    register_reviews,
    register_update,
    register_uploads,
)
from .report_usage import (
    register_report_usage,
)
from .source_link import register_source_link
from .taxonomy_handler import register_taxonomy


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``courses`` subcommand group."""
    parser = subparsers.add_parser("courses", help="Manage courses")
    sub = parser.add_subparsers(
        dest="courses_command",
        required=True,
    )

    register_create(sub)
    register_get(sub)
    register_mine(sub)
    register_update(sub)
    register_uploads(sub)
    register_publication(sub)
    register_purchase(sub)
    register_reviews(sub)
    register_report_usage(sub)
    register_capabilities(sub)
    register_package_map(sub)
    register_source_link(sub)
    register_taxonomy(sub)
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

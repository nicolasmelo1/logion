# SPDX-License-Identifier: MIT
"""Parser registration for course-reviews commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import (
    handle_approve,
    handle_download,
    handle_get,
    handle_list,
    handle_reject,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``course-reviews`` subcommand group."""
    parser = subparsers.add_parser(
        "course-reviews",
        help="Manage course publication review queue",
    )
    sub = parser.add_subparsers(
        dest="course_reviews_command",
        required=True,
    )

    list_parser = sub.add_parser(
        "list",
        help="List actionable review queue items",
        parents=[COMMON_PARSER],
    )
    list_parser.add_argument("--limit", type=int)
    list_parser.add_argument("--cursor")
    list_parser.set_defaults(handler=handle_list)

    get = sub.add_parser(
        "get",
        help="Get review queue item details",
        parents=[COMMON_PARSER],
    )
    get.add_argument("review_id", metavar="REVIEW_ID")
    get.set_defaults(handler=handle_get)

    approve = sub.add_parser(
        "approve",
        help="Approve a publication review",
        parents=[COMMON_PARSER],
    )
    approve.add_argument("review_id", metavar="REVIEW_ID")
    approve.add_argument("--reviewer-notes")
    approve.add_argument(
        "--acknowledge-capability-mismatches",
        action="store_true",
        help="Acknowledge capability mismatches on the review",
    )
    approve.add_argument("--yes", action="store_true")
    approve.set_defaults(handler=handle_approve)

    reject = sub.add_parser(
        "reject",
        help="Reject a publication review",
        parents=[COMMON_PARSER],
    )
    reject.add_argument("review_id", metavar="REVIEW_ID")
    reject.add_argument("--decision-reason", required=True)
    reject.add_argument("--reviewer-notes", required=True)
    reject.add_argument(
        "--capability-reason-code",
        help="Code from the review's capability mismatches",
    )
    reject.add_argument("--yes", action="store_true")
    reject.set_defaults(handler=handle_reject)

    download = sub.add_parser(
        "download",
        help=(
            "Download the bundle under review to a local directory "
            "so SKILL.md and references can be read before deciding"
        ),
        parents=[COMMON_PARSER],
    )
    download.add_argument("review_id", metavar="REVIEW_ID")
    download.add_argument(
        "--target",
        help=(
            "Directory to write the bundle into "
            "(default: ./review-bundles/<review-id>/)"
        ),
    )
    download.set_defaults(handler=handle_download)

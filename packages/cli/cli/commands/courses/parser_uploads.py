# SPDX-License-Identifier: MIT
"""Parser registration for ``courses uploads`` subcommands.

Lives in its own module so :mod:`parser_sections` stays under the
per-file line budget.
"""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from ._uploads_push import handle_uploads_push
from .handlers import handle_uploads_complete, handle_uploads_create


def register_uploads(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``uploads`` subcommand group."""
    uploads = subparsers.add_parser("uploads", help="Manage course uploads")
    uploads_sub = uploads.add_subparsers(
        dest="courses_uploads_command",
        required=True,
    )

    create = uploads_sub.add_parser(
        "create",
        help="Create an upload session for a course version",
        parents=[COMMON_PARSER],
    )
    create.add_argument("course_id", metavar="COURSE_ID")
    create.add_argument(
        "--file",
        action="append",
        dest="files",
        default=[],
        help=(
            "File path to include in the upload session. "
            "Use FILE_PATH or UPLOAD_PATH=FILE_PATH to override the upload "
            "path. When omitted, only the basename is used and directory "
            "structure is flattened."
        ),
    )
    create.set_defaults(handler=handle_uploads_create)

    complete = uploads_sub.add_parser(
        "complete",
        help="Complete an upload session",
        parents=[COMMON_PARSER],
    )
    complete.add_argument("course_id", metavar="COURSE_ID")
    complete.add_argument("version_id", metavar="VERSION_ID")
    complete.set_defaults(handler=handle_uploads_complete)

    push = uploads_sub.add_parser(
        "push",
        help="PUT each file in an upload session to its presigned URL",
        parents=[COMMON_PARSER],
    )
    push.add_argument("course_id", metavar="COURSE_ID")
    push.add_argument("version_id", metavar="VERSION_ID")
    push.add_argument(
        "--session-file",
        required=True,
        help=(
            "Path to the JSON returned by `uploads create`; use '-' to read "
            "from stdin."
        ),
    )
    push.add_argument(
        "--file",
        action="append",
        dest="files",
        default=[],
        help=(
            "Local file to push. Use UPLOAD_PATH=LOCAL_PATH (matched against "
            "the session's `filename`) or LOCAL_PATH for basename matching. "
            "Repeatable."
        ),
    )
    # --max-retries and --timeout come from COMMON_PARSER; defaults are
    # applied in the handler so push has sensible behaviour even when
    # the caller omits them.
    push.set_defaults(handler=handle_uploads_push)

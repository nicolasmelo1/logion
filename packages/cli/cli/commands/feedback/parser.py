# SPDX-License-Identifier: MIT
"""Parser registration for feedback commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import (
    handle_feedback_list,
    handle_feedback_submit,
    handle_feedback_summary,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``feedback`` subcommand group."""
    parser = subparsers.add_parser(
        "feedback",
        help="Submit and list resource-use feedback",
    )
    sub = parser.add_subparsers(
        dest="feedback_command",
        required=True,
    )

    # feedback submit
    submit = sub.add_parser(
        "submit",
        help="Submit feedback for a resource version",
        parents=[COMMON_PARSER],
    )
    submit.add_argument("resource_id", metavar="RESOURCE_ID")
    submit.add_argument("version_id", metavar="VERSION_ID")
    submit.add_argument(
        "--rating", type=int, choices=range(1, 6), required=True
    )
    submit.add_argument("--usefulness", type=int, default=None)
    submit.add_argument("--reliability", type=int, default=None)
    submit.add_argument(
        "--tool-safety",
        dest="tool_safety",
        type=int,
        default=None,
    )
    submit.add_argument(
        "--acquisition-channel",
        dest="acquisition_channel",
        default=None,
        help=(
            "Override the channel; resolved from the local acquisition"
            " receipt when omitted."
        ),
    )
    submit.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Revise feedback already submitted for this version/task class.",
    )
    submit.add_argument("--source-receipt-id", default=None)
    submit.add_argument(
        "--token-efficiency",
        dest="token_efficiency",
        type=int,
        default=None,
    )
    submit.add_argument(
        "--completed-task",
        dest="completed_task",
        action="store_true",
        default=False,
    )
    submit.add_argument(
        "--not-completed-task",
        dest="completed_task",
        action="store_false",
    )
    submit.add_argument(
        "--task-class",
        dest="task_class",
        required=True,
    )
    submit.add_argument("--body", default=None)
    submit.set_defaults(handler=handle_feedback_submit)

    # feedback list
    lst = sub.add_parser(
        "list",
        help="List your submitted feedback",
        parents=[COMMON_PARSER],
    )
    lst.add_argument("--mine", action="store_true", default=True)
    lst.set_defaults(handler=handle_feedback_list)

    # feedback summary
    summary = sub.add_parser(
        "summary",
        help="Show aggregated feedback for a resource",
        parents=[COMMON_PARSER],
    )
    summary.add_argument("resource_id", metavar="RESOURCE_ID")
    summary.set_defaults(handler=handle_feedback_summary)

# SPDX-License-Identifier: MIT
"""Agent-driven review convenience command."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, validate_uuid_id
from cli._output import emit_json
from cli._utils import only_not_none

from .reviews import _validate_review_scores


def handle_report_usage(args: argparse.Namespace) -> int:
    """Execute the courses report-usage command.

    Thin convenience wrapper over ``reviews upsert`` for the agent-driven
    review loop.  Same guardrails (entitlement-required, self-review-blocked)
    apply because the call is forwarded to the same API endpoint.
    """
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.version_id, "VERSION_ID")
    if bad_id is not None:
        return bad_id
    review_scores_error = _validate_review_scores(args)
    if review_scores_error is not None:
        return review_scores_error

    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {
                "course_id": args.course_id,
                "version_id": args.version_id,
                "rating": args.rating,
            },
            body=args.body,
            completed_task=args.completed_task,
            reliability=args.reliability,
            usefulness=args.usefulness,
            tool_safety=args.tool_safety,
            token_efficiency=args.token_efficiency,
        )
        result = client.v1.courses.review_version(**kwargs)
        data = {
            "course_id": args.course_id,
            "version_id": args.version_id,
            "persisted_fields": [
                k for k, v in kwargs.items() if v is not None
            ],
        }
        result_data = {}
        if hasattr(result, "model_dump"):
            result_data = result.model_dump()
        elif hasattr(result, "__dict__"):
            result_data = {
                k: v
                for k, v in result.__dict__.items()
                if not k.startswith("_")
            }
        if "review_id" in result_data:
            data["review_id"] = result_data["review_id"]
        emit_json("logion.courses.report-usage", data)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def register_report_usage(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``courses report-usage`` subcommand."""
    parser = subparsers.add_parser(
        "report-usage",
        help="File a usage review after completing a course-driven task",
        parents=[],
    )
    parser.add_argument("course_id", metavar="COURSE_ID")
    parser.add_argument("version_id", metavar="VERSION_ID")
    parser.add_argument(
        "--rating",
        type=int,
        required=True,
        help="Overall rating 1-5 (required).",
    )
    parser.add_argument(
        "--body",
        default=None,
        help="Short narrative: what worked, what didn't.",
    )
    completed = parser.add_mutually_exclusive_group()
    completed.add_argument(
        "--completed-task",
        action="store_true",
        default=None,
        dest="completed_task",
        help="The task finished successfully.",
    )
    completed.add_argument(
        "--not-completed-task",
        action="store_false",
        default=None,
        dest="completed_task",
        help="The task did not finish.",
    )
    parser.add_argument(
        "--reliability",
        type=float,
        default=None,
        help="Did the course work without surprises? 0.0-5.0.",
    )
    parser.add_argument(
        "--usefulness",
        type=float,
        default=None,
        help="Did the course content help with the task? 0.0-5.0.",
    )
    parser.add_argument(
        "--tool-safety",
        type=float,
        default=None,
        help="Did it stay within declared capabilities? 0.0-5.0.",
    )
    parser.add_argument(
        "--token-efficiency",
        type=float,
        default=None,
        help="Subjective token cost impression. 0.0-5.0.",
    )
    parser.set_defaults(handler=handle_report_usage)

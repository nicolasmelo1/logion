"""Review handlers for courses commands."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import (
    handle_error,
    print_err,
    validate_uuid_id,
)
from cli._output import emit, emit_json, to_data
from cli._utils import only_not_none
from cli.commands.courses._capability_render import (
    append_capability_feedback_lines,
)
from cli.commands.courses._review_helpers import (
    collect_reviews,
    compact_review,
    compute_summary,
    data_or_model_dump,
)

REVIEW_SCORE_FIELDS = [
    ("reliability", "--reliability"),
    ("usefulness", "--usefulness"),
    ("tool_safety", "--tool-safety"),
    ("token_efficiency", "--token-efficiency"),
]

_DEFAULT_LIST_LIMIT = 5
_MAX_LIST_LIMIT = 50


def _validate_review_scores(args: argparse.Namespace) -> int | None:
    if not (1 <= args.rating <= 5):
        print_err("Error: --rating must be between 1 and 5.")
        return 2
    for attr, label in REVIEW_SCORE_FIELDS:
        value = getattr(args, attr)
        if value is not None and not (0.0 <= value <= 5.0):
            print_err(f"Error: {label} must be between 0.0 and 5.0.")
            return 2
    return None


def handle_reviews_list(args: argparse.Namespace) -> int:
    """Execute the courses reviews list command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        limit = min(
            max(args.limit or _DEFAULT_LIST_LIMIT, 1),
            _MAX_LIST_LIMIT,
        )
        kwargs = only_not_none(
            {"course_id": args.course_id},
            version=args.version,
            limit=limit,
            cursor=args.cursor,
        )
        result = client.v1.courses.list_reviews(**kwargs)
        if config.json_output:
            data = data_or_model_dump(result)
            reviews = [
                compact_review(review)
                for review in data.get("reviews", [])
                if isinstance(review, dict)
            ]
            emit_json(
                "logion.courses.reviews.list",
                {
                    "items": reviews,
                    "limit": kwargs["limit"],
                    "next_cursor": data.get("next_cursor"),
                },
            )
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reviews_mine(args: argparse.Namespace) -> int:
    """Execute the courses reviews mine command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    if args.version_id is not None:
        bad_id = validate_uuid_id(args.version_id, "--version-id")
        if bad_id is not None:
            return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {"course_id": args.course_id},
            version_id=args.version_id,
        )
        result = client.v1.courses.get_my_review(**kwargs)
        if config.json_output:
            data = data_or_model_dump(result)
            emit_json("logion.courses.reviews.mine", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reviews_upsert(args: argparse.Namespace) -> int:
    """Execute the courses reviews upsert command."""
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
        if config.json_output:
            data = data_or_model_dump(result)
            emit_json("logion.courses.reviews.upsert", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reviews_summary(args: argparse.Namespace) -> int:
    """Compute aggregate review statistics for a course."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        limit = min(
            max(args.limit or _DEFAULT_LIST_LIMIT, 1),
            _MAX_LIST_LIMIT,
        )
        all_reviews = collect_reviews(
            client,
            args.course_id,
            version=getattr(args, "version", None),
            limit=limit,
        )
        summary = compute_summary(args.course_id, all_reviews)
        if config.json_output:
            emit_json("logion.courses.reviews.summary", summary)
        else:
            lines: list[str] = [
                f"course_id: {summary['course_id']}",
                f"review_count: {summary['review_count']}",
                f"rating_avg: {summary['rating_avg']}",
                f"rating_histogram: {summary['rating_histogram']}",
            ]
            sys.stdout.write("\n".join(lines))
            sys.stdout.write("\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_feedback(args: argparse.Namespace) -> int:
    """Execute the courses feedback command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.get_review_feedback(
            course_id=args.course_id,
        )
        if config.json_output:
            data = data_or_model_dump(result)
            emit_json("logion.courses.feedback", data)
        else:
            data = to_data(result)
            lines: list[str] = []
            if data.get("summary"):
                lines.append(f"summary: {data['summary']}")
            if data.get("findings"):
                lines.append("findings:")
                for f in data["findings"]:
                    lines.append(f"  - {f}")
            append_capability_feedback_lines(lines, data)
            if not lines:
                lines.append("No feedback available.")
            sys.stdout.write("\n".join(lines))
            sys.stdout.write("\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

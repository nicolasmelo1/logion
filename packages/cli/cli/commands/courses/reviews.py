"""Review handlers for courses commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._output import emit
from cli._utils import only_not_none

REVIEW_SCORE_FIELDS = [
    ("reliability", "--reliability"),
    ("usefulness", "--usefulness"),
    ("tool_safety", "--tool-safety"),
    ("token_efficiency", "--token-efficiency"),
]


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
        kwargs = only_not_none(
            {"course_id": args.course_id},
            version=args.version,
            limit=args.limit,
            cursor=args.cursor,
        )
        result = client.v1.courses.list_reviews(**kwargs)
        emit(result, json_output=config.json_output)
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
        emit(result, json_output=config.json_output)
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
        emit(result, json_output=config.json_output)
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
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

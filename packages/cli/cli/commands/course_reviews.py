"""Course-reviews commands — human review queue management."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error
from cli._options import COMMON_PARSER
from cli._output import emit


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

    # ── list ────────────────────────────────────────────────────
    ls = sub.add_parser(
        "list",
        help="List actionable review queue items",
        parents=[COMMON_PARSER],
    )
    ls.add_argument("--limit", type=int)
    ls.add_argument("--cursor")
    ls.set_defaults(handler=handle_list)

    # ── get ──────────────────────────────────────────────────────
    get = sub.add_parser(
        "get",
        help="Get review queue item details",
        parents=[COMMON_PARSER],
    )
    get.add_argument("review_id")
    get.set_defaults(handler=handle_get)

    # ── approve ─────────────────────────────────────────────────
    approve = sub.add_parser(
        "approve",
        help="Approve a publication review",
        parents=[COMMON_PARSER],
    )
    approve.add_argument("review_id")
    approve.add_argument("--reviewer-notes")
    approve.add_argument("--yes", action="store_true")
    approve.set_defaults(handler=handle_approve)

    # ── reject ──────────────────────────────────────────────────
    reject = sub.add_parser(
        "reject",
        help="Reject a publication review",
        parents=[COMMON_PARSER],
    )
    reject.add_argument("review_id")
    reject.add_argument("--decision-reason", required=True)
    reject.add_argument("--reviewer-notes", required=True)
    reject.add_argument("--yes", action="store_true")
    reject.set_defaults(handler=handle_reject)


def handle_list(args: argparse.Namespace) -> int:
    """Execute course-reviews list."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.course_reviews.list(
            limit=args.limit,
            cursor=args.cursor,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_get(args: argparse.Namespace) -> int:
    """Execute course-reviews get."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.course_reviews.get(review_id=args.review_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_approve(args: argparse.Namespace) -> int:
    """Execute course-reviews approve."""
    refusal = require_yes(args.yes, "approve")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.course_reviews.approve(
            review_id=args.review_id,
            reviewer_notes=args.reviewer_notes,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reject(args: argparse.Namespace) -> int:
    """Execute course-reviews reject."""
    refusal = require_yes(args.yes, "reject")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.course_reviews.reject(
            review_id=args.review_id,
            decision_reason=args.decision_reason,
            reviewer_notes=args.reviewer_notes,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

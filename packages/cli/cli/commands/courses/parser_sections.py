# SPDX-License-Identifier: MIT
"""Subparser builders for courses commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from ._cmd_help import CMD_HELP
from .handlers import (
    handle_create,
    handle_get,
    handle_publication_latest,
    handle_publication_request,
    handle_purchase,
    handle_reviews_list,
    handle_reviews_mine,
    handle_reviews_summary,
    handle_reviews_upsert,
    handle_update,
)
from .parser_uploads import register_uploads as _register_uploads
from .parser_utils import (
    add_category_argument,
    add_tag_arguments,
    add_tristate_flag,
)

# Re-export for existing imports.
register_uploads = _register_uploads


def register_create(subparsers: argparse._SubParsersAction) -> None:
    create = subparsers.add_parser(
        "create",
        help=CMD_HELP["create"],
        parents=[COMMON_PARSER],
    )
    create.add_argument("--title", required=True)
    create.add_argument("--slug", required=True)
    create.add_argument("--description")
    create.add_argument("--price-cents", type=int)
    create.add_argument("--currency")
    add_tag_arguments(create, default=[])
    add_category_argument(create)
    create.add_argument("--language")
    create.add_argument("--short-summary")
    create.add_argument(
        "--visibility", choices=["public", "unlisted", "private"]
    )
    create.set_defaults(handler=handle_create)


def register_get(subparsers: argparse._SubParsersAction) -> None:
    get = subparsers.add_parser(
        "get",
        help=CMD_HELP["get"],
        parents=[COMMON_PARSER],
    )
    get.add_argument("course_id", metavar="COURSE_ID")
    get.set_defaults(handler=handle_get)


def register_update(subparsers: argparse._SubParsersAction) -> None:
    update = subparsers.add_parser(
        "update",
        help=CMD_HELP["update"],
        parents=[COMMON_PARSER],
    )
    update.add_argument("course_id", metavar="COURSE_ID")
    update.add_argument("--title")

    description = update.add_mutually_exclusive_group()
    description.add_argument("--description")
    description.add_argument(
        "--clear-description",
        action="store_true",
        help="Clear the course description",
    )

    price = update.add_mutually_exclusive_group()
    price.add_argument("--price-cents", type=int)
    price.add_argument(
        "--clear-price",
        action="store_true",
        help=(
            "Clear the course price (price_cents and currency). "
            "Note: this also clears the currency."
        ),
    )

    currency = update.add_mutually_exclusive_group()
    currency.add_argument("--currency")
    currency.add_argument(
        "--clear-currency",
        action="store_true",
        help="Clear the course currency",
    )

    language = update.add_mutually_exclusive_group()
    language.add_argument("--language")
    language.add_argument(
        "--clear-language",
        action="store_true",
        help="Clear the course language",
    )

    short_summary = update.add_mutually_exclusive_group()
    short_summary.add_argument("--short-summary")
    short_summary.add_argument(
        "--clear-short-summary",
        action="store_true",
        help="Clear the short summary",
    )

    add_tag_arguments(update, default=None)
    add_category_argument(update)
    update.add_argument(
        "--visibility", choices=["public", "unlisted", "private"]
    )
    update.set_defaults(handler=handle_update)


def register_publication(subparsers: argparse._SubParsersAction) -> None:
    publication = subparsers.add_parser(
        "publication",
        help=CMD_HELP["publication"],
    )
    pub_sub = publication.add_subparsers(
        dest="courses_publication_command",
        required=True,
    )

    request = pub_sub.add_parser(
        "request",
        help="Request publication review",
        parents=[COMMON_PARSER],
    )
    request.add_argument("course_id", metavar="COURSE_ID")
    request.set_defaults(handler=handle_publication_request)

    latest = pub_sub.add_parser(
        "latest",
        help="Get latest publication review status",
        parents=[COMMON_PARSER],
    )
    latest.add_argument("course_id", metavar="COURSE_ID")
    add_tristate_flag(latest, "--include-pass", dest="include_pass")
    latest.set_defaults(handler=handle_publication_latest)


def register_reviews(subparsers: argparse._SubParsersAction) -> None:
    reviews = subparsers.add_parser("reviews", help=CMD_HELP["reviews"])
    reviews_sub = reviews.add_subparsers(
        dest="courses_reviews_command",
        required=True,
    )

    list_parser = reviews_sub.add_parser(
        "list",
        help="List reviews for a course",
        parents=[COMMON_PARSER],
    )
    list_parser.add_argument("course_id", metavar="COURSE_ID")
    list_parser.add_argument("--version")
    list_parser.add_argument("--limit", type=int, default=5)
    list_parser.add_argument("--cursor")
    list_parser.set_defaults(handler=handle_reviews_list)

    mine = reviews_sub.add_parser(
        "mine",
        help="Get your review for a course version",
        parents=[COMMON_PARSER],
    )
    mine.add_argument("course_id", metavar="COURSE_ID")
    mine.add_argument("--version-id")
    mine.set_defaults(handler=handle_reviews_mine)

    upsert = reviews_sub.add_parser(
        "upsert",
        help="Create or update a review for a course version",
        parents=[COMMON_PARSER],
    )
    upsert.add_argument("course_id", metavar="COURSE_ID")
    upsert.add_argument("version_id", metavar="VERSION_ID")
    upsert.add_argument("--rating", type=int, required=True)
    upsert.add_argument("--body")
    add_tristate_flag(upsert, "--completed-task", dest="completed_task")
    upsert.add_argument("--reliability", type=float)
    upsert.add_argument("--usefulness", type=float)
    upsert.add_argument("--tool-safety", type=float)
    upsert.add_argument("--token-efficiency", type=float)
    upsert.set_defaults(handler=handle_reviews_upsert)

    summary = reviews_sub.add_parser(
        "summary",
        help="Show aggregate review statistics for a course",
        parents=[COMMON_PARSER],
    )
    summary.add_argument("course_id", metavar="COURSE_ID")
    summary.add_argument("--version")
    summary.add_argument("--limit", type=int, default=5)
    summary.set_defaults(handler=handle_reviews_summary)


def register_purchase(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``courses purchase`` subcommand."""
    purchase = subparsers.add_parser(
        "purchase",
        help=CMD_HELP["purchase"],
        parents=[COMMON_PARSER],
    )
    purchase.add_argument("course_id", metavar="COURSE_ID")
    purchase.add_argument(
        "--expected-price-cents",
        dest="expected_price_cents",
        type=int,
        default=None,
        help=(
            "Price guard: fail if the course price has"
            " changed. Omit to skip the guard (the --yes"
            " confirmation still protects against"
            " accidental purchases)."
        ),
    )
    purchase.add_argument(
        "--idempotency-key",
        dest="idempotency_key",
        default=None,
        help="Optional idempotency key to safely retry a purchase.",
    )
    purchase.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Confirm the purchase without prompting.",
    )
    purchase.set_defaults(handler=handle_purchase)

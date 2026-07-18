# SPDX-License-Identifier: MIT
"""Parser registration for listings commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import handle_search

_SORT_CHOICES = [
    "relevance",
    "newest",
    "recently_updated",
    "price_low",
    "price_high",
    "most_useful",
]


def register(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register the ``listings`` subcommand group."""
    parser = subparsers.add_parser("listings", help="Search course listings")
    sub = parser.add_subparsers(
        dest="listings_command",
        required=True,
    )

    search = sub.add_parser(
        "search",
        help="Search course listings",
        parents=[COMMON_PARSER],
    )
    search.add_argument("--query")
    tag_group = search.add_mutually_exclusive_group()
    tag_group.add_argument(
        "--tag",
        action="append",
        dest="tag_filters",
        default=None,
        help="Filter by tag (repeatable; AND semantics)",
    )
    tag_group.add_argument(
        "--tags",
        dest="tags",
        help="Filter by tags (comma-separated; use --tag instead)",
    )
    search.add_argument("--category")
    search.add_argument("--language")
    search.add_argument("--price-min", type=int)
    search.add_argument("--price-max", type=int)
    search.add_argument("--sort", choices=_SORT_CHOICES)
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--verbose", action="store_true", default=False)
    search.add_argument("--cursor")
    search.add_argument(
        "--include-indexed",
        action="store_true",
        default=False,
        help="Include indexed external listings in search results",
    )
    search.add_argument(
        "--tier",
        choices=["published", "indexed", "improving"],
        help=(
            "Filter by listing tier: published (default), "
            "indexed, or improving"
        ),
    )
    search.set_defaults(handler=handle_search)

    return parser

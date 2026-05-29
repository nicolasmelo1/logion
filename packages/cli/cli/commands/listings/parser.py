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


def register(subparsers: argparse._SubParsersAction) -> None:
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
    search.add_argument("--tags")
    search.add_argument("--language")
    search.add_argument("--price-min", type=int)
    search.add_argument("--price-max", type=int)
    search.add_argument("--sort", choices=_SORT_CHOICES)
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--verbose", action="store_true", default=False)
    search.add_argument("--cursor")
    search.set_defaults(handler=handle_search)

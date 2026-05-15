"""Listings command — search the marketplace."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._options import add_common_options
from cli._output import emit


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``listings`` subcommand group."""
    parser = subparsers.add_parser("listings", help="Search course listings")
    add_common_options(parser)
    sub = parser.add_subparsers(
        dest="listings_command",
        required=True,
    )

    search = sub.add_parser("search", help="Search course listings")
    add_common_options(search)
    search.add_argument("--query")
    search.add_argument("--tags")
    search.add_argument("--language")
    search.add_argument("--price-min", type=int)
    search.add_argument("--price-max", type=int)
    search.add_argument(
        "--sort",
        choices=[
            "relevance",
            "newest",
            "recently_updated",
            "price_low",
            "price_high",
            "most_useful",
        ],
    )
    search.add_argument("--limit", type=int)
    search.add_argument("--cursor")
    search.set_defaults(handler=handle_search)


def handle_search(args: argparse.Namespace) -> int:
    """Execute the listings search."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.listings.search(
            query=args.query,
            tags=args.tags,
            language=getattr(args, "language", None),
            price_min=getattr(args, "price_min", None),
            price_max=getattr(args, "price_max", None),
            sort=args.sort,
            limit=args.limit,
            cursor=getattr(args, "cursor", None),
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

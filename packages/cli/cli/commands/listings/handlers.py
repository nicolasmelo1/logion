"""Handlers for listings commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._output import emit


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

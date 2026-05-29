"""Handlers for listings commands."""

from __future__ import annotations

import argparse
import json
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._output import emit_json, to_data, truncate_summary

_DEFAULT_LIMIT = 5
_MAX_LIMIT = 50


def _compact_match(item: dict[str, object]) -> dict[str, object]:
    """Build the compact listing payload for default JSON output."""
    summary_source = item.get("short_summary") or item.get("summary")
    tags_value = item.get("tags")
    tags = tags_value[:5] if isinstance(tags_value, list) else []
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "summary": truncate_summary(
            summary_source if isinstance(summary_source, str) else None
        ),
        "tags": tags,
        "price": {
            "amount_cents": item.get("price_cents"),
            "currency": item.get("currency"),
        },
        "status": item.get("status", "published"),
    }


def _format_search_payload(
    result: object, *, limit: int, verbose: bool
) -> dict[str, object]:
    """Normalise the SDK response into the CLI's stable payload shape."""
    data = to_data(result)
    if isinstance(data, dict):
        raw_items = data.get("items", [])
        next_cursor = data.get("next_cursor")
    else:
        raw_items = []
        next_cursor = None

    items = [item for item in raw_items if isinstance(item, dict)]
    matches = items if verbose else [_compact_match(item) for item in items]
    payload: dict[str, object] = {
        "matches": matches,
        "total": len(items),
        "limit": limit,
    }
    if next_cursor is not None:
        payload["next_cursor"] = next_cursor
    return payload


def handle_search(args: argparse.Namespace) -> int:
    """Execute the listings search."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    requested_limit = getattr(args, "limit", _DEFAULT_LIMIT) or _DEFAULT_LIMIT
    limit = min(max(requested_limit, 1), _MAX_LIMIT)
    try:
        result = client.v1.listings.search(
            query=args.query,
            tags=args.tags,
            language=getattr(args, "language", None),
            price_min=getattr(args, "price_min", None),
            price_max=getattr(args, "price_max", None),
            sort=args.sort,
            limit=limit,
            cursor=getattr(args, "cursor", None),
        )
        payload = _format_search_payload(
            result,
            limit=limit,
            verbose=getattr(args, "verbose", False),
        )
        if config.json_output:
            emit_json("logion.listings.search", payload)
        else:
            sys.stdout.write(f"{json.dumps(payload, indent=2)}\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

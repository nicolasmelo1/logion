# SPDX-License-Identifier: MIT
"""Handlers for listings commands."""

from __future__ import annotations

import argparse

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
        "status": (
            item["tier"] if "tier" in item else item.get("status", "published")
        ),
        "external": item.get("external", False),
        "source_url": item.get("source_url"),
        "source_hub": item.get("source_hub"),
        "license_spdx": item.get("license_spdx"),
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


def _print_human(payload: dict[str, object]) -> None:
    """Render a compact human-readable search result list."""
    matches = payload.get("matches")
    if not isinstance(matches, list) or not matches:
        from sys import stdout

        stdout.write("No listings found.\n")
        return

    from sys import stdout

    stdout.write(f"Listings ({payload.get('total', len(matches))}):\n")
    for match in matches:
        if not isinstance(match, dict):
            continue
        listing_id = match.get("id", "?")
        title = match.get("title", "")
        summary = match.get("summary", "")
        price_value = match.get("price")
        price = price_value if isinstance(price_value, dict) else {}
        amount = price.get("amount_cents")
        currency = price.get("currency")
        status = match.get("status", "unknown")

        line = f"  {listing_id}"
        if title:
            line += f" — {title}"
        if amount is not None and currency:
            line += f" [{amount} {currency}]"
        line += f" [{status}]"
        if match.get("external"):
            line += " [external]"
        stdout.write(f"{line}\n")
        source_url = match.get("source_url")
        if isinstance(source_url, str) and source_url:
            stdout.write(f"    Source: {source_url}\n")
        if isinstance(summary, str) and summary:
            stdout.write(f"    {summary}\n")


def handle_search(args: argparse.Namespace) -> int:
    """Execute the listings search."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    requested_limit = getattr(args, "limit", _DEFAULT_LIMIT) or _DEFAULT_LIMIT
    limit = min(max(requested_limit, 1), _MAX_LIMIT)
    # The API accepts a comma-separated tags string. --tag (repeatable)
    # is the preferred CLI form; --tags is the legacy comma form.
    tag_filters = getattr(args, "tag_filters", None)
    tags_param = args.tags
    if tag_filters:
        tags_param = ",".join(tag_filters)
    category = getattr(args, "category", None)
    sort = args.sort or ("relevance" if args.query else None)
    try:
        result = client.v1.listings.search(
            query=args.query,
            tags=tags_param,
            category=category,
            language=getattr(args, "language", None),
            price_min=getattr(args, "price_min", None),
            price_max=getattr(args, "price_max", None),
            sort=sort,
            limit=limit,
            cursor=getattr(args, "cursor", None),
            include_indexed=getattr(args, "include_indexed", False),
            tier=getattr(args, "tier", None),
        )
        payload = _format_search_payload(
            result,
            limit=limit,
            verbose=getattr(args, "verbose", False),
        )
        if config.json_output:
            emit_json("logion.listings.search", payload)
        else:
            _print_human(payload)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

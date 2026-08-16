# SPDX-License-Identifier: MIT
"""Handler for ``logion skills search``.

Searches marketplace listings via the API and annotates each result
with entitlement status derived from locally installed manifests.
"""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._json import JsonObject, JsonValue, elements, opt_str
from cli._local_state import VALID_ENTITLEMENT_STATUSES, list_installed
from cli._output import emit_json, truncate_summary

from ._install_helpers import resolve_target


def _normalize_items(result: JsonValue) -> list[JsonObject]:
    """Convert SDK response items to plain dicts."""
    # Prefer dict key 'items' over the dict method
    if isinstance(result, dict):
        raw = elements(result, "items")
    elif hasattr(result, "items") and not isinstance(result, dict):
        raw = getattr(result, "items", result)
        if callable(raw):
            raw = result
    else:
        raw = result

    items: list[JsonObject] = []
    if isinstance(raw, list):
        inner = raw
    elif isinstance(raw, dict):
        inner = raw.get("items", [raw])
    else:
        return items

    for item in inner:
        if hasattr(item, "model_dump"):
            items.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            items.append(dict(item))
        else:
            items.append({"value": item})
    return items


def _annotate_entitlement(
    items: list[JsonObject],
    installed_manifests: list[JsonObject],
) -> list[JsonObject]:
    """Add ``entitlement_status`` to each item based on installed data."""
    entitlement_map: dict[str, str] = {}
    for m in installed_manifests:
        cid = opt_str(m, "course_id", "")
        entitlement_map[cid] = opt_str(m, "entitlement_status", "unknown")

    for item in items:
        course_id = item.get("course_id")
        if not isinstance(course_id, str) or not course_id:
            item["entitlement_status"] = "unknown"
            continue
        if course_id in entitlement_map:
            status = entitlement_map[course_id]
            if status in VALID_ENTITLEMENT_STATUSES:
                item["entitlement_status"] = status
            else:
                item["entitlement_status"] = "unknown"
        else:
            item["entitlement_status"] = "missing"
    return items


def _print_human(items: list[JsonObject], verbose: bool) -> None:
    """Print compact human-readable results."""
    if not items:
        print("No results found.")
        return
    print(f"Search results ({len(items)}):")
    for item in items:
        course_id = item.get("course_id", opt_str(item, "id", "?"))
        title = opt_str(item, "title", "")
        summary = truncate_summary(
            item.get("short_summary") or item.get("summary") or ""
        )
        status = opt_str(item, "entitlement_status", "unknown")
        line = f"  {course_id}"
        if title:
            line += f" — {title}"
        line += f" [{status}]"
        if summary:
            line += f"\n    {summary}"
        print(line, file=sys.stdout)
    if verbose:
        import json as _json

        for item in items:
            print(_json.dumps(item, indent=2, sort_keys=True))


def handle_skills_search(args: argparse.Namespace) -> int:
    """Search marketplace listings with installed/entitlement annotations."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    home = resolve_target(args)

    installed_manifests = list_installed(home)

    try:
        result = client.v1.listings.search(
            query=args.query,
            limit=args.limit,
            sort="relevance",
        )
    except Exception as exc:
        return handle_error(exc)
    finally:
        client.close()

    items = _normalize_items(result)
    items = _annotate_entitlement(items, installed_manifests)

    if config.json_output:
        emit_json(
            "logion.skills.search",
            {"items": items, "total": len(items)},
        )
    else:
        verbose = getattr(args, "verbose", False)
        _print_human(items, verbose)

    return 0

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
from cli._json import JsonObject, opt_str
from cli._local_state import VALID_ENTITLEMENT_STATUSES, list_installed
from cli._output import emit_json, to_data, truncate_summary

from ._install_helpers import resolve_target


def _normalize_items(result: object) -> list[JsonObject]:
    """Convert an SDK collection response to plain dicts.

    ``to_data`` unwraps the model and handles both collection
    encodings, replacing a hand-rolled getattr/callable probe that
    existed only to avoid mistaking a mapping's ``.items`` method for
    an ``items`` field.

    A non-object entry is still wrapped as ``{"value": ...}`` rather
    than dropped, so a malformed row stays visible in the listing.
    """
    data = to_data(result)
    if isinstance(data, dict):
        data = data.get("items", [data])
    if not isinstance(data, list):
        return []
    return [
        dict(item) if isinstance(item, dict) else {"value": item}
        for item in data
    ]


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
        course_id = opt_str(item, "course_id") or opt_str(item, "id", "?")
        title = opt_str(item, "title", "")
        summary = truncate_summary(
            opt_str(item, "short_summary") or opt_str(item, "summary")
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

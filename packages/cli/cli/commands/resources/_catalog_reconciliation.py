# SPDX-License-Identifier: MIT
"""Catalog matching for native manager reconciliation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cli._json import JsonObject, opt_str
from cli._lazy_import import LazyModule
from cli._output import to_data, to_items

if TYPE_CHECKING:
    import logion
else:
    logion = LazyModule("logion")


def catalog_matches(
    client: logion.LogionClient, item: JsonObject
) -> list[JsonObject]:
    """Resolve native source/revision against the paginated catalog."""
    source = str(item.get("source") or "")
    revision = str(item.get("revision") or "")
    resource_type = {
        "skills": "agent_skill",
        "plugins": "agent_plugin",
        "dsh": "agent_plugin",
        "hf": "model",
    }.get(str(item.get("manager") or ""))
    if not source or resource_type is None:
        return []
    matches: list[JsonObject] = []
    cursor: str | None = None
    while True:
        try:
            payload = to_data(
                client.v1.resources.search(
                    resource_type=resource_type, limit=100, cursor=cursor
                )
            )
        except Exception:
            return []
        for resource in to_items(payload):
            matches.extend(
                _resource_version_matches(client, resource, source, revision)
            )
        if isinstance(payload, list):
            break
        page = payload if isinstance(payload, dict) else {}
        cursor_value = opt_str(page, "next_cursor") or opt_str(
            page, "nextCursor"
        )
        if not cursor_value or cursor_value == cursor:
            break
        cursor = cursor_value
    return matches


#: Locator prefixes different surfaces use for the same Git source. They
#: are normalized away so comparison stays exact instead of substring
#: based — `owner/repo` must never match `owner/repo-extra`.
_LOCATOR_PREFIXES = (
    "https://github.com/",
    "http://github.com/",
    "git@github.com:",
    "github:",
    "gh:",
)


def normalize_locator(value: str) -> str:
    """Reduce a Git locator to a comparable ``owner/repo`` identity."""
    text = str(value or "").strip().lower()
    for prefix in _LOCATOR_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.removesuffix(".git")
    # A `#skill` fragment is catalog identity, not part of the repository.
    text = text.partition("#")[0].strip("/")
    # A `/tree/<ref>` or `/blob/<ref>` path is a GitHub-specific ref selector,
    # not part of the repository identity. Strip it so a commit-pinned URL
    # matches the bare ``owner/repo`` the catalog stores.
    for sep in ("/tree/", "/blob/", "/commit/"):
        idx = text.find(sep)
        if idx > 0:
            text = text[:idx].strip("/")
    return text


def _resource_version_matches(
    client: logion.LogionClient,
    resource: JsonObject,
    source: str,
    revision: str,
) -> list[JsonObject]:
    canonical = str(resource.get("canonical_uri") or "")
    # Exact identity only. Fuzzy or display-name linking silently
    # attributes an installation to the wrong resource.
    if normalize_locator(canonical) != normalize_locator(source):
        return []
    resource_id = resource.get("id")
    if not resource_id:
        return []
    try:
        versions = to_data(
            client.v1.resources.versions(resource_id=str(resource_id))
        )
    except Exception:
        return []
    matches: list[JsonObject] = []
    for version in to_items(versions):
        version_revision = str(version.get("source_revision") or "")
        if revision and version_revision and revision != version_revision:
            continue
        matches.append({
            "resource_id": str(resource_id),
            "resource_type": str(resource.get("resource_type") or ""),
            "version_id": str(
                version.get("id") or version.get("version_id") or ""
            ),
            "verification": (
                "source_revision"
                if revision and version_revision
                else "canonical_source"
            ),
        })
    return matches

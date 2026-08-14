# SPDX-License-Identifier: MIT
"""Catalog matching for native manager reconciliation."""

from __future__ import annotations

from typing import Any

from cli._output import to_data


def catalog_matches(
    client: Any, item: dict[str, object]
) -> list[dict[str, object]]:
    """Resolve native source/revision against the paginated catalog."""
    source = str(item.get("source") or "")
    revision = str(item.get("revision") or "")
    resource_type = {
        "skills": "agent_skill",
        "plugins": "agent_plugin",
        "hf": "model",
    }.get(str(item.get("manager") or ""))
    if not source or resource_type is None:
        return []
    matches: list[dict[str, object]] = []
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
        entries = (
            payload if isinstance(payload, list) else payload.get("items", [])
        )
        for resource in entries:
            if isinstance(resource, dict):
                matches.extend(
                    _resource_version_matches(
                        client, resource, source, revision
                    )
                )
        if isinstance(payload, list):
            break
        cursor_value = payload.get("next_cursor") or payload.get("nextCursor")
        if not cursor_value or cursor_value == cursor:
            break
        cursor = str(cursor_value)
    return matches


def _resource_version_matches(
    client: Any,
    resource: dict[str, object],
    source: str,
    revision: str,
) -> list[dict[str, object]]:
    canonical = str(resource.get("canonical_uri") or "")
    if (
        canonical != source
        and source not in canonical
        and canonical not in source
    ):
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
    versions = (
        versions if isinstance(versions, list) else versions.get("items", [])
    )
    matches: list[dict[str, object]] = []
    for version in versions:
        if not isinstance(version, dict):
            continue
        version_revision = str(version.get("source_revision") or "")
        if revision and version_revision and revision != version_revision:
            continue
        matches.append({
            "resource_id": str(resource_id),
            "version_id": str(
                version.get("id") or version.get("version_id") or ""
            ),
            "verification": "source_revision" if revision else "canonical",
        })
    return matches

# SPDX-License-Identifier: MIT
"""API resolution helpers for ``logion instrument``.

Extracted from ``_plan.py`` to keep source files under the
250-line architecture limit.
"""

from __future__ import annotations

import re

from cli._json import JsonObject, as_object, collection
from cli._output import to_data


def resolve_resource_version(
    client: object,
    resource_version_input: str,
) -> tuple[JsonObject, JsonObject]:
    """Resolve a canonical ResourceVersion from the API.

    Accepts either a bare resource UUID or a ``urn:air:...@version``
    compound identifier. Returns the resource detail and the selected
    version as a tuple.
    """
    if "@" in resource_version_input:
        resource_part, version_part = resource_version_input.rsplit("@", 1)
    else:
        resource_part = resource_version_input
        version_part = None

    raw_resource = to_data(
        client.v1.resources.get(  # type: ignore[attr-defined]
            resource_id=resource_part,
        )
    )
    resource_obj = as_object(raw_resource)
    nested = resource_obj.get("resource")
    resource = nested if isinstance(nested, dict) else resource_obj

    raw_versions = to_data(
        client.v1.resources.versions(  # type: ignore[attr-defined]
            resource_id=resource_part,
        )
    )
    versions = collection(raw_versions)
    if not versions:
        raise ValueError(
            f"no versions available for resource {resource_part!r}"
        )

    if version_part:
        selected: JsonObject | None = None
        for v in versions:
            if str(v.get("id") or v.get("version_id") or "") == version_part:
                selected = v
                break
            if str(v.get("version") or "") == version_part:
                selected = v
                break
        if selected is None:
            raise ValueError(
                f"version {version_part!r} not found for resource "
                f"{resource_part!r}"
            )
    else:
        selected = versions[0]

    return resource, selected


def resource_slug(resource: JsonObject, version: JsonObject) -> str:
    """Derive a slug from the resource title or canonical URI."""
    raw = (
        resource.get("title")
        or resource.get("canonical_uri")
        or version.get("version")
        or "resource"
    )
    normalized = re.sub(r"[^a-z0-9._-]+", "-", str(raw).lower()).strip("-.")
    return normalized[:128] if normalized else "resource"

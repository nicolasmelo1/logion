# SPDX-License-Identifier: MIT
"""Dedup: merge discoveries by canonical id, query API, emit plan.

Merges all discoveries from all hubs into one record per canonical
skill (unioning channels), queries the API ``known`` endpoint for
existing listings, and emits a plan: ``create[]``, ``update[]``,
``skip[]`` with reasons.

Both skill-centric (``CanonicalSkillId``) and generic
(``CanonicalResourceId``) paths are provided.  The skill path is
preserved for backwards compatibility; the resource path is the
preferred entry point for new code.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from urllib.parse import quote

from .canonical import CanonicalResourceId, CanonicalSkillId
from .models import DiscoveredResource, DiscoveredSkill
from .transport import Transport

# Known kinds returned by the API.
KIND_INDEXED_LISTING = "indexed_listing"
KIND_COURSE = "course"
KIND_CLAIMED = "claimed"

SKIP_REASONS = {
    "already_logion_course": "already_logion_course",
    "already_claimed": "already_claimed",
    "no_change": "no_change",
}
KNOWN_BATCH_SIZE = 25


# ---------------------------------------------------------------------------
# Skill-centric plan (legacy)
# ---------------------------------------------------------------------------


@dataclass
class DedupPlan:
    """Plan output: what to create, update, and skip.

    ``create`` / ``update`` hold full :class:`DiscoveredSkill` objects and
    are serialized verbatim in :meth:`to_dict` (the same serialization the
    pusher sends), so a plan file is a complete, resume-able push payload.
    """

    create: list[DiscoveredSkill] = field(default_factory=list)
    update: list[DiscoveredSkill] = field(default_factory=list)
    skip: list[dict] = field(default_factory=list)
    partial: bool = False

    @property
    def total(self) -> int:
        return len(self.create) + len(self.update) + len(self.skip)

    def to_dict(self) -> dict:
        from .pusher import serialize_item

        return {
            "create": [serialize_item(s) for s in self.create],
            "update": [serialize_item(s) for s in self.update],
            "skip": self.skip,
            "partial": self.partial,
        }

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), indent=2)


def merge_discoveries(
    discoveries: Iterable[DiscoveredSkill],
) -> list[DiscoveredSkill]:
    """Merge discoveries by canonical id, unioning channels.

    A skill listed on three hubs collapses into one record with
    three discovery channels.
    """
    merged: dict[CanonicalSkillId, DiscoveredSkill] = {}

    for d in discoveries:
        key = d.canonical
        if key not in merged:
            merged[key] = d
        else:
            existing = merged[key]
            # Union channels.
            all_channels = list(set(existing.channels) | set(d.channels))
            all_channels.sort(key=lambda c: (c.hub_slug, c.hub_url))
            # Pick the best metadata (prefer non-empty fields).
            title = existing.title or d.title
            summary = existing.summary or d.summary
            license_spdx = existing.license_spdx or d.license_spdx
            source_commit = existing.source_commit or d.source_commit
            original_author = existing.original_author or d.original_author
            tags = tuple(sorted(set(existing.tags) | set(d.tags)))
            inferred_map = existing.inferred_map or d.inferred_map
            map_flags = tuple(
                sorted(set(existing.map_flags) | set(d.map_flags))
            )
            bundle = existing.bundle or d.bundle
            merged[key] = DiscoveredSkill(
                canonical=key,
                title=title,
                summary=summary,
                original_author=original_author,
                license_spdx=license_spdx,
                source_commit=source_commit,
                tags=tags,
                channels=tuple(all_channels),
                inferred_map=inferred_map,
                map_flags=map_flags,
                bundle=bundle,
            )

    return list(merged.values())


def query_known(
    canonical_ids: Sequence[CanonicalSkillId],
    transport: Transport,
    base_url: str,
) -> dict[str, dict]:
    """Query the API ``known`` endpoint for existing listings.

    Returns ``{canonical_str: {kind, id}}``.
    """
    if not canonical_ids:
        return {}

    known: dict[str, dict] = {}
    url = f"{base_url.rstrip('/')}/v1/admin/indexing/known"
    for offset in range(0, len(canonical_ids), KNOWN_BATCH_SIZE):
        batch = canonical_ids[offset : offset + KNOWN_BATCH_SIZE]
        ids_param = ",".join(quote(str(cid), safe="") for cid in batch)
        resp = transport.get(
            f"{url}?ids={ids_param}",
            use_cache=False,
        )
        if resp.status != 200:
            raise RuntimeError(
                f"known-listing lookup failed: HTTP {resp.status}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(
                "known-listing lookup returned invalid JSON"
            ) from exc
        if not isinstance(data, dict):
            raise TypeError("known-listing lookup returned invalid data")
        batch_known = data.get("known")
        if not isinstance(batch_known, dict):
            raise TypeError("known-listing lookup omitted known map")
        for canonical, info in batch_known.items():
            if not isinstance(canonical, str) or not isinstance(info, dict):
                raise TypeError(
                    "known-listing lookup returned an invalid map entry"
                )
            known[canonical] = info
    return known


def build_plan(
    merged: list[DiscoveredSkill],
    known: dict[str, dict],
) -> DedupPlan:
    """Build a plan from merged discoveries and the known map.

    - ``indexed_listing`` → update (commit moved or channels changed).
    - ``course`` → skip, reason ``already_logion_course``.
    - ``claimed`` → skip, reason ``already_claimed``.
    - absent → create.
    """
    plan = DedupPlan()

    for skill in merged:
        cid = str(skill.canonical)
        info = known.get(cid)

        if info is None:
            plan.create.append(skill)
        elif info.get("kind") == KIND_INDEXED_LISTING:
            plan.update.append(skill)
        elif info.get("kind") == KIND_COURSE:
            plan.skip.append({
                "canonical": cid,
                "reason": SKIP_REASONS["already_logion_course"],
            })
        elif info.get("kind") == KIND_CLAIMED:
            plan.skip.append({
                "canonical": cid,
                "reason": SKIP_REASONS["already_claimed"],
            })
        else:
            plan.create.append(skill)

    return plan


def dedup(
    discoveries: Iterable[DiscoveredSkill],
    transport: Transport,
    base_url: str,
) -> DedupPlan:
    """Full dedup pipeline: merge → query known → build plan."""
    merged = merge_discoveries(discoveries)
    known = query_known([d.canonical for d in merged], transport, base_url)
    return build_plan(merged, known)


def dry_run_plan(
    discoveries: Iterable[DiscoveredSkill],
    transport: Transport,
    base_url: str,
) -> DedupPlan:
    """Build a plan without any POSTs (dry-run mode).

    Queries the ``known`` endpoint (GET) but never pushes.
    """
    return dedup(discoveries, transport, base_url)


# ---------------------------------------------------------------------------
# Resource-centric plan (generic)
# ---------------------------------------------------------------------------


@dataclass
class ResourceDedupPlan:
    """Plan output for generic resources: what to create, update, and skip.

    Like :class:`DedupPlan` but keyed by :class:`CanonicalResourceId`
    and carrying :class:`DiscoveredResource` objects.
    """

    create: list[DiscoveredResource] = field(default_factory=list)
    update: list[DiscoveredResource] = field(default_factory=list)
    skip: list[dict] = field(default_factory=list)
    partial: bool = False

    @property
    def total(self) -> int:
        return len(self.create) + len(self.update) + len(self.skip)

    def to_dict(self) -> dict:
        from .pusher import serialize_resource_item

        return {
            "create": [serialize_resource_item(r) for r in self.create],
            "update": [serialize_resource_item(r) for r in self.update],
            "skip": self.skip,
            "partial": self.partial,
        }

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), indent=2)


def merge_resource_discoveries(
    discoveries: Iterable[DiscoveredResource],
) -> list[DiscoveredResource]:
    """Merge discoveries by (resource_type, canonical_uri), unioning channels.

    A resource listed on multiple hubs collapses into one record with
    all discovery channels.
    """
    merged: dict[CanonicalResourceId, DiscoveredResource] = {}

    for d in discoveries:
        key = d.canonical
        if key not in merged:
            merged[key] = d
        else:
            existing = merged[key]
            all_channels = list(set(existing.channels) | set(d.channels))
            all_channels.sort(key=lambda c: (c.hub_slug, c.hub_url))
            title = existing.title or d.title
            summary = existing.summary or d.summary
            license_spdx = existing.license_spdx or d.license_spdx
            source_commit = existing.source_commit or d.source_commit
            original_author = existing.original_author or d.original_author
            tags = tuple(sorted(set(existing.tags) | set(d.tags)))
            inferred_map = existing.inferred_map or d.inferred_map
            map_flags = tuple(
                sorted(set(existing.map_flags) | set(d.map_flags))
            )
            bundle = existing.bundle or d.bundle
            merged[key] = DiscoveredResource(
                canonical=key,
                resource_type=existing.resource_type,
                canonical_uri=existing.canonical_uri,
                title=title,
                summary=summary,
                original_author=original_author,
                license_spdx=license_spdx,
                source_commit=source_commit,
                tags=tags,
                channels=tuple(all_channels),
                inferred_map=inferred_map,
                map_flags=map_flags,
                bundle=bundle,
            )

    return list(merged.values())


def query_known_resources(
    canonical_ids: Sequence[CanonicalResourceId],
    transport: Transport,
    base_url: str,
) -> dict[str, dict]:
    """Query the API ``known`` endpoint for existing resources.

    Returns ``{canonical_str: {kind, id}}``.
    """
    if not canonical_ids:
        return {}

    known: dict[str, dict] = {}
    url = f"{base_url.rstrip('/')}/v1/admin/indexing/known"
    for offset in range(0, len(canonical_ids), KNOWN_BATCH_SIZE):
        batch = canonical_ids[offset : offset + KNOWN_BATCH_SIZE]
        ids_param = ",".join(quote(str(cid), safe="") for cid in batch)
        resp = transport.get(
            f"{url}?ids={ids_param}",
            use_cache=False,
        )
        if resp.status != 200:
            raise RuntimeError(
                f"known-resource lookup failed: HTTP {resp.status}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(
                "known-resource lookup returned invalid JSON"
            ) from exc
        if not isinstance(data, dict):
            raise TypeError("known-resource lookup returned invalid data")
        batch_known = data.get("known")
        if not isinstance(batch_known, dict):
            raise TypeError("known-resource lookup omitted known map")
        for canonical, info in batch_known.items():
            if not isinstance(canonical, str) or not isinstance(info, dict):
                raise TypeError(
                    "known-resource lookup returned an invalid map entry"
                )
            known[canonical] = info
    return known


def build_resource_plan(
    merged: list[DiscoveredResource],
    known: dict[str, dict],
) -> ResourceDedupPlan:
    """Build a plan from merged resource discoveries and the known map.

    Same logic as :func:`build_plan` but for
    :class:`DiscoveredResource` objects.
    """
    plan = ResourceDedupPlan()

    for resource in merged:
        cid = str(resource.canonical)
        info = known.get(cid)

        if info is None:
            plan.create.append(resource)
        elif info.get("kind") == KIND_INDEXED_LISTING:
            plan.update.append(resource)
        elif info.get("kind") == KIND_COURSE:
            plan.skip.append({
                "canonical": cid,
                "reason": SKIP_REASONS["already_logion_course"],
            })
        elif info.get("kind") == KIND_CLAIMED:
            plan.skip.append({
                "canonical": cid,
                "reason": SKIP_REASONS["already_claimed"],
            })
        else:
            plan.create.append(resource)

    return plan


def dedup_resources(
    discoveries: Iterable[DiscoveredResource],
    transport: Transport,
    base_url: str,
) -> ResourceDedupPlan:
    """Full dedup pipeline for resources: merge → query known → build plan."""
    merged = merge_resource_discoveries(discoveries)
    known = query_known_resources(
        [d.canonical for d in merged], transport, base_url
    )
    return build_resource_plan(merged, known)

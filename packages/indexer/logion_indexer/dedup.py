"""Dedup: merge discoveries by CanonicalSkillId, query API, emit plan.

Merges all discoveries from all hubs into one record per canonical
skill (unioning channels), queries the API ``known`` endpoint for
existing listings, and emits a plan: ``create[]``, ``update[]``,
``skip[]`` with reasons.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from .canonical import CanonicalSkillId
from .models import DiscoveredSkill
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


@dataclass
class DedupPlan:
    """Plan output: what to create, update, and skip."""

    create: list[DiscoveredSkill] = field(default_factory=list)
    update: list[DiscoveredSkill] = field(default_factory=list)
    skip: list[dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.create) + len(self.update) + len(self.skip)

    def to_dict(self) -> dict:
        return {
            "create": [str(s.canonical) for s in self.create],
            "update": [str(s.canonical) for s in self.update],
            "skip": self.skip,
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

    ids_param = ",".join(str(cid) for cid in canonical_ids)
    url = f"{base_url.rstrip('/')}/v1/admin/indexing/known"
    # Pass ids as query parameter.
    full_url = f"{url}?ids={ids_param}"
    resp = transport.get(full_url)
    if resp.status != 200:
        return {}

    data = resp.json()
    if not isinstance(data, dict):
        return {}
    known = data.get("known") or {}
    if not isinstance(known, dict):
        return {}
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

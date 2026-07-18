"""Indexing pipeline: discover -> enrich -> validate -> mirror -> plan.

Ties the stages together so both ``crawl`` (plan only) and ``run`` (plan
+ push) share one code path:

1. merge discoveries by canonical id (union channels),
2. enrich map-less hub discoveries into per-component items (attaching
   inferred maps via the shared :class:`GithubSource`),
3. re-merge (a repo listed on several hubs collapses again),
4. validate every ``inferred_map`` fragment through ``logion_skillmap``;
   drop invalid ones and mark the run partial,
5. mirror permissive-license bundles (tarball -> runtime.include subtree
   -> deterministic repack) and flag skills-lock drift,
6. query the ``known`` endpoint and build the create/update/skip plan.

The mirrored bundle *bytes* are returned alongside the plan (keyed by
canonical id) so the pusher can upload them after upsert; they are not
serialized into the plan file.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.error import URLError

from .dedup import DedupPlan, build_plan, merge_discoveries, query_known
from .enrichment import enrich_discoveries
from .github_source import GithubSource, is_permissive_license
from .mirror import BundleArtifact, mirror_bundle_for
from .models import DiscoveredSkill, DiscoveryChannel
from .transport import Transport
from .validation import INFERRED_MAP_INVALID, fragment_errors


def build_indexing_plan(
    discoveries: Iterable[DiscoveredSkill],
    transport: Transport,
    base_url: str,
    *,
    source: GithubSource | None = None,
    mirror: bool = True,
) -> tuple[DedupPlan, dict[str, BundleArtifact]]:
    """Run the full pipeline and return ``(plan, bundle_artifacts)``."""
    source = source or GithubSource(transport=transport)

    merged = merge_discoveries(discoveries)
    enriched, skips = enrich_discoveries(merged, source)
    remerged = merge_discoveries(enriched)

    valid: list[DiscoveredSkill] = []
    partial = bool(skips)
    for skill in remerged:
        errors = fragment_errors(skill.inferred_map)
        if errors:
            partial = True
            skips.append({
                "canonical": str(skill.canonical),
                "reason": INFERRED_MAP_INVALID,
                "codes": errors,
            })
            continue
        valid.append(skill)

    artifacts: dict[str, BundleArtifact] = {}
    if mirror:
        valid = [_mirror_and_flag(skill, source, artifacts) for skill in valid]

    known = query_known([s.canonical for s in valid], transport, base_url)
    plan = build_plan(valid, known)
    plan.skip.extend(skips)
    plan.partial = partial
    return plan, artifacts


def _mirror_and_flag(
    skill: DiscoveredSkill,
    source: GithubSource,
    artifacts: dict[str, BundleArtifact],
) -> DiscoveredSkill:
    """Mirror a permissive bundle and flag skills-lock drift.

    Returns the item with ``bundle`` metadata attached (when mirrored)
    and any ``lock_drift`` channel signal set.  On a restricted license or
    a failed/oversized mirror the item stays link-only, with the reason
    recorded in ``map_flags``.
    """
    canonical = str(skill.canonical)
    tarball = None
    if skill.source_commit and is_permissive_license(skill.license_spdx):
        try:
            tarball = source.fetch_tarball(
                skill.canonical.owner,
                skill.canonical.repo,
                skill.source_commit,
            )
        except (URLError, TimeoutError):
            # Network exhaustion keeps the listing link-only; a single CDN
            # failure must not discard metadata for the entire run.
            tarball = None
    artifact, reason = mirror_bundle_for(
        canonical, skill.license_spdx, skill.inferred_map, tarball
    )

    bundle_meta = skill.bundle
    map_flags = skill.map_flags
    bundle_sha = ""
    if artifact is not None:
        artifacts[canonical] = artifact
        bundle_meta = artifact.meta()
        bundle_sha = artifact.sha256
    elif reason is not None:
        map_flags = tuple(sorted(set(map_flags) | {reason}))

    channels = _apply_lock_drift(skill.channels, bundle_sha)

    return DiscoveredSkill(
        canonical=skill.canonical,
        title=skill.title,
        summary=skill.summary,
        original_author=skill.original_author,
        license_spdx=skill.license_spdx,
        source_commit=skill.source_commit,
        tags=skill.tags,
        channels=channels,
        inferred_map=skill.inferred_map,
        map_flags=map_flags,
        bundle=bundle_meta,
    )


def _apply_lock_drift(
    channels: tuple[DiscoveryChannel, ...],
    bundle_sha: str,
) -> tuple[DiscoveryChannel, ...]:
    """Set ``lock_drift=true`` on skills-lock channels on hash mismatch.

    Compares our mirrored bundle sha at HEAD against the lockfile's
    ``computedHash``.  Display signal only — it gates nothing.
    """
    if not bundle_sha:
        return channels
    out: list[DiscoveryChannel] = []
    for ch in channels:
        meta = dict(ch.metadata)
        computed = meta.get("computedHash", "")
        if computed and computed != bundle_sha:
            meta["lock_drift"] = "true"
            ch = DiscoveryChannel(
                hub_slug=ch.hub_slug,
                hub_url=ch.hub_url,
                hub_verified=ch.hub_verified,
                metadata=tuple(sorted(meta.items())),
            )
        out.append(ch)
    return tuple(out)

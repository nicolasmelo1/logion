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
   -> deterministic repack),
6. query the ``known`` endpoint and build the create/update/skip plan.

The mirrored bundle *bytes* are returned alongside the plan (keyed by
canonical id) so the pusher can upload them after upsert; they are not
serialized into the plan file.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from urllib.error import URLError

from .canonical import CanonicalSkillId
from .dedup import (
    DedupPlan,
    ResourceDedupPlan,
    build_plan,
    build_resource_plan,
    merge_discoveries,
    merge_resource_discoveries,
    query_known,
    query_known_resources,
)
from .enrichment import enrich_discoveries
from .github_source import GithubSource, is_permissive_license
from .mirror import BundleArtifact, mirror_bundle_for
from .models import DiscoveredResource, DiscoveredSkill
from .transport import Transport
from .validation import INFERRED_MAP_INVALID, fragment_errors


def partition_discoveries(
    discoveries: Iterable[DiscoveredSkill | DiscoveredResource],
) -> tuple[list[DiscoveredSkill], list[DiscoveredResource]]:
    """Split a crawl into the skill and generic-resource vocabularies.

    A seed file mixes adapters of both kinds, and the two go through
    different pipelines. Splitting keeps one adapter's vocabulary from
    discarding another's discoveries.
    """
    skills: list[DiscoveredSkill] = []
    resources: list[DiscoveredResource] = []
    for item in discoveries:
        if isinstance(item, DiscoveredResource):
            resources.append(item)
        else:
            skills.append(item)
    return skills, resources


def build_resource_indexing_plan(
    resources: Iterable[DiscoveredResource],
    transport: Transport,
    base_url: str,
    *,
    source: GithubSource | None = None,
    digest: bool = True,
) -> ResourceDedupPlan:
    """Plan generic resources, pinning a content digest without hosting.

    Resource artifacts are never mirrored — Logion does not host or
    redistribute another ecosystem's plugins. The digest is still
    computed from the pinned revision, because without one the catalog
    cannot mint a version and therefore cannot carry any distribution.
    """
    source = source or GithubSource(transport=transport)
    merged = merge_resource_discoveries(resources)
    if digest:
        merged = [_digest_resource(item, source) for item in merged]
    known = query_known_resources(
        [item.canonical for item in merged], transport, base_url
    )
    return build_resource_plan(merged, known)


def build_indexing_plan(
    discoveries: Iterable[DiscoveredSkill],
    transport: Transport,
    base_url: str,
    *,
    source: GithubSource | None = None,
    mirror: bool = True,
    workers: int = 4,
) -> tuple[DedupPlan, dict[str, BundleArtifact]]:
    """Run the skill pipeline and return ``(plan, bundle_artifacts)``."""
    source = source or GithubSource(transport=transport)
    skills, _ = partition_discoveries(discoveries)
    merged = merge_discoveries(skills)
    enriched, skips = enrich_discoveries(merged, source, workers=workers)
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
        valid = [_mirror_skill(skill, source, artifacts) for skill in valid]

    known = query_known([s.canonical for s in valid], transport, base_url)
    plan = build_plan(valid, known)
    plan.skip.extend(skips)
    plan.partial = partial
    return plan, artifacts


def _digest_resource(
    resource: DiscoveredResource,
    source: GithubSource,
) -> DiscoveredResource:
    """Attach a content digest derived from the pinned revision.

    The bundle is built only to hash it: the artifact is discarded and
    never uploaded, so the catalog gains an integrity pin without Logion
    hosting or redistributing the resource.
    """
    if resource.bundle or not resource.source_commit:
        return resource
    canonical = CanonicalSkillId.from_str(resource.canonical_uri)
    try:
        tarball = source.fetch_tarball(
            canonical.owner, canonical.repo, resource.source_commit
        )
    except (URLError, TimeoutError, ValueError):
        # A digest Logion could not compute is simply absent; the listing
        # stays acquisition-less rather than carrying an invented pin.
        return resource
    artifact, _reason = mirror_bundle_for(
        resource.canonical_uri,
        resource.license_spdx,
        resource.inferred_map,
        tarball,
    )
    if artifact is None:
        return resource
    return replace(resource, bundle=artifact.meta())


def _mirror_skill(
    skill: DiscoveredSkill,
    source: GithubSource,
    artifacts: dict[str, BundleArtifact],
) -> DiscoveredSkill:
    """Mirror a permissive bundle when policy and source data allow it.

    On a restricted license or a failed/oversized mirror the item stays
    link-only, with the reason recorded in ``map_flags``.
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
    if artifact is not None:
        artifacts[canonical] = artifact
        bundle_meta = artifact.meta()
    elif reason is not None:
        map_flags = tuple(sorted(set(map_flags) | {reason}))

    return DiscoveredSkill(
        canonical=skill.canonical,
        title=skill.title,
        summary=skill.summary,
        original_author=skill.original_author,
        license_spdx=skill.license_spdx,
        source_commit=skill.source_commit,
        tags=skill.tags,
        channels=skill.channels,
        inferred_map=skill.inferred_map,
        map_flags=map_flags,
        bundle=bundle_meta,
    )

"""Enrichment: attach inferred maps to hub discoveries."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from http.client import RemoteDisconnected
from itertools import repeat
from urllib.error import URLError

from .github_source import GithubSource, InferredSkill
from .models import DiscoveredSkill, DiscoveryChannel

SKIP_NO_GITHUB_SOURCE = "no_github_source"
SKIP_NO_COMPONENTS = "no_components"
SKIP_GITHUB_NETWORK_ERROR = "github_network_error"


def enrich_discoveries(
    discoveries: Iterable[DiscoveredSkill],
    source: GithubSource,
    *,
    workers: int = 4,
) -> tuple[list[DiscoveredSkill], list[dict]]:
    """Attach inferred maps concurrently while preserving input order.

    Each repository enrichment is independent. Results are consumed in input
    order so plans and diagnostics stay deterministic despite network timing.
    """
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        results = list(executor.map(_enrich_one, discoveries, repeat(source)))

    items: list[DiscoveredSkill] = []
    skips: list[dict] = []
    for result_items, result_skips in results:
        items.extend(result_items)
        skips.extend(result_skips)
    return items, skips


def _enrich_one(
    disc: DiscoveredSkill, source: GithubSource
) -> tuple[list[DiscoveredSkill], list[dict]]:
    if disc.inferred_map is not None:
        return [disc], []

    canonical = disc.canonical
    owner, repo = canonical.owner, canonical.repo
    try:
        sha = source.fetch_head_sha(owner, repo)
    except (RemoteDisconnected, URLError, TimeoutError):
        return [], [_skip(canonical, SKIP_GITHUB_NETWORK_ERROR)]
    if not sha:
        return [], [_skip(canonical, SKIP_NO_GITHUB_SOURCE)]

    try:
        license_spdx = source.fetch_license(owner, repo)
        _, skills = source.infer_skills(
            owner, repo, sha=sha, subpath=canonical.subpath
        )
    except (RemoteDisconnected, URLError, TimeoutError):
        return [], [_skip(canonical, SKIP_GITHUB_NETWORK_ERROR)]
    if not skills:
        return [], [_skip(canonical, SKIP_NO_COMPONENTS)]

    return [
        _expand(disc, skill, license_spdx=license_spdx, source_commit=sha)
        for skill in skills
    ], []


def _skip(canonical, reason: str) -> dict:
    return {"canonical": str(canonical), "reason": reason}


def _expand(
    disc: DiscoveredSkill,
    skill: InferredSkill,
    *,
    license_spdx: str | None,
    source_commit: str,
) -> DiscoveredSkill:
    """Build one per-component item from a hub discovery + inferred skill."""
    channels: tuple[DiscoveryChannel, ...] = disc.channels or (
        DiscoveryChannel(
            hub_slug="github",
            hub_url=f"https://github.com/{disc.canonical.owner}"
            f"/{disc.canonical.repo}",
        ),
    )
    return DiscoveredSkill(
        canonical=skill.canonical,
        title=skill.name or disc.title,
        summary=skill.summary or disc.summary,
        original_author=disc.canonical.owner,
        license_spdx=license_spdx,
        source_commit=source_commit or None,
        tags=disc.tags,
        channels=channels,
        inferred_map=skill.inferred_map,
        map_flags=skill.map_flags,
    )

"""Enrichment: attach inferred maps to hub discoveries.

Hub adapters (lobehub, clawhub, skills.sh, browse.sh, hermes, skills-lock)
resolve a listing to a GitHub identity but do not run inference, so they
emit ``inferred_map=None``.  This stage makes every such discovery behave
exactly like ``github_direct``: it fetches repo metadata and runs
``logion_skillmap.infer()`` via the shared, sha-cached
:class:`GithubSource`, expanding the repo into one item per canonical
skillmap component and unioning the hub's discovery channels onto each.

Discoveries that already carry a map (``github_direct``) pass through
untouched.  Repos with no fetchable GitHub source, or that yield zero
components, are dropped with a recorded skip reason.
"""

from __future__ import annotations

from collections.abc import Iterable
from http.client import RemoteDisconnected
from urllib.error import URLError

from .github_source import GithubSource, InferredSkill
from .models import DiscoveredSkill, DiscoveryChannel

SKIP_NO_GITHUB_SOURCE = "no_github_source"
SKIP_NO_COMPONENTS = "no_components"
SKIP_GITHUB_NETWORK_ERROR = "github_network_error"


def enrich_discoveries(
    discoveries: Iterable[DiscoveredSkill],
    source: GithubSource,
) -> tuple[list[DiscoveredSkill], list[dict]]:
    """Attach inferred maps to map-less discoveries.

    Returns ``(items, skips)`` where *items* is the pass-through
    already-mapped discoveries plus the per-component expansions of the
    map-less ones, and *skips* records dropped repos with reasons.
    """
    items: list[DiscoveredSkill] = []
    skips: list[dict] = []

    for disc in discoveries:
        if disc.inferred_map is not None:
            items.append(disc)
            continue

        canonical = disc.canonical
        owner, repo = canonical.owner, canonical.repo
        try:
            sha = source.fetch_head_sha(owner, repo)
        except (RemoteDisconnected, URLError, TimeoutError):
            skips.append({
                "canonical": str(canonical),
                "reason": SKIP_GITHUB_NETWORK_ERROR,
            })
            continue
        if not sha:
            skips.append({
                "canonical": str(canonical),
                "reason": SKIP_NO_GITHUB_SOURCE,
            })
            continue

        try:
            license_spdx = source.fetch_license(owner, repo)
            _, skills = source.infer_skills(
                owner, repo, sha=sha, subpath=canonical.subpath
            )
        except (RemoteDisconnected, URLError, TimeoutError):
            skips.append({
                "canonical": str(canonical),
                "reason": SKIP_GITHUB_NETWORK_ERROR,
            })
            continue
        if not skills:
            skips.append({
                "canonical": str(canonical),
                "reason": SKIP_NO_COMPONENTS,
            })
            continue

        for skill in skills:
            items.append(
                _expand(
                    disc,
                    skill,
                    license_spdx=license_spdx,
                    source_commit=sha,
                )
            )

    return items, skips


def _expand(
    disc: DiscoveredSkill,
    skill: InferredSkill,
    *,
    license_spdx: str | None,
    source_commit: str,
) -> DiscoveredSkill:
    """Build one per-component item from a hub discovery + inferred skill.

    Title/summary come from SKILL.md frontmatter (carried on the inferred
    skill); the hub's text is used only as a fallback.  The
    ``skillmap_frontmatter_missing`` flag, when relevant, is already among
    ``skill.map_flags``.  The hub's discovery channels are preserved.
    """
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

"""Data models for the indexer: discovered skills and channels."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import CanonicalSkillId


@dataclass(frozen=True)
class DiscoveryChannel:
    """A single hub where a skill was seen.

    Attributes:
        hub_slug: Short identifier for the hub (e.g. ``lobehub``).
        hub_url: The URL where the skill was listed on this hub.
        hub_verified: Whether the hub marks this listing as verified.
        metadata: Optional adapter-specific metadata (e.g. lockfile
            ``computedHash`` for the skills-lock adapter).
    """

    hub_slug: str
    hub_url: str
    hub_verified: bool = False
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DiscoveredSkill:
    """A skill discovered from one or more hubs.

    Attributes:
        canonical: The canonical GitHub identity.
        title: Skill title (from SKILL.md frontmatter via skillmap).
        summary: One-line description (from frontmatter).
        original_author: GitHub owner login.
        license_spdx: SPDX license string or None.
        source_commit: HEAD SHA at crawl time, or None.
        tags: Tuple of tag strings.
        channels: Tuple of discovery channels (hubs where seen).
        inferred_map: Per-skill package-map fragment (15.3 schema),
            or None if inference failed.
        map_flags: Skillmap needs_review codes, verbatim.
        bundle: Mirrored-bundle metadata ``{sha256, size_bytes}`` when a
            permissive-license bundle was mirrored, else None (link-only).
    """

    canonical: CanonicalSkillId
    title: str = ""
    summary: str = ""
    original_author: str = ""
    license_spdx: str | None = None
    source_commit: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    channels: tuple[DiscoveryChannel, ...] = field(default_factory=tuple)
    inferred_map: dict | None = None
    map_flags: tuple[str, ...] = field(default_factory=tuple)
    bundle: dict | None = None

# SPDX-License-Identifier: MIT
"""Data models for the indexer: discovered resources and channels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .canonical import CanonicalResourceId, CanonicalSkillId


@dataclass(frozen=True)
class DiscoveryChannel:
    """A single hub where a skill was seen.

    Attributes:
        hub_slug: Short identifier for the hub (e.g. ``clawhub``).
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
class DiscoveredResource:
    """A resource discovered from one or more hubs.

    This is the generic successor to :class:`DiscoveredSkill`, supporting
    skill, plugin, MCP server, model, and course resource types.

    Attributes:
        canonical: The canonical resource identity.
        resource_type: Resource type discriminator (``skill``, ``plugin``,
            ``mcp_server``, ``model``, ``course``).
        canonical_uri: The normalised URI for this resource (e.g.
            ``gh:owner/repo`` for GitHub-hosted skills).
        title: Resource title.
        summary: One-line description.
        original_author: Original author login.
        license_spdx: SPDX license string or None.
        source_commit: HEAD SHA at crawl time, or None.
        tags: Tuple of tag strings.
        channels: Tuple of discovery channels (hubs where seen).
        inferred_map: Per-resource package-map fragment, or None.
        map_flags: Skillmap needs_review codes, verbatim.
        bundle: Mirrored-bundle metadata when available, else None.
        declared_capabilities: What the publisher's own manifest declares
            (``{tools, patch}``), never what Logion verified.
    """

    canonical: CanonicalResourceId
    resource_type: str = "skill"
    canonical_uri: str = ""
    title: str = ""
    summary: str = ""
    original_author: str = ""
    license_spdx: str | None = None
    source_commit: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    channels: tuple[DiscoveryChannel, ...] = field(default_factory=tuple)
    inferred_map: dict[str, Any] | None = None
    map_flags: tuple[str, ...] = field(default_factory=tuple)
    bundle: dict[str, Any] | None = None
    declared_capabilities: dict[str, Any] | None = None


@dataclass(frozen=True)
class DiscoveredSkill:
    """A skill discovered from one or more hubs.

    .. deprecated::
        Use :class:`DiscoveredResource` instead.  ``DiscoveredSkill``
        is kept as a compatibility alias that wraps
        :class:`DiscoveredResource` internally.

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
    inferred_map: dict[str, Any] | None = None
    map_flags: tuple[str, ...] = field(default_factory=tuple)
    bundle: dict[str, Any] | None = None

    def to_resource(self) -> DiscoveredResource:
        """Convert to a :class:`DiscoveredResource`."""
        canonical_id = CanonicalResourceId.from_skill_id(self.canonical)
        return DiscoveredResource(
            canonical=canonical_id,
            resource_type="skill",
            canonical_uri=str(self.canonical),
            title=self.title,
            summary=self.summary,
            original_author=self.original_author,
            license_spdx=self.license_spdx,
            source_commit=self.source_commit,
            tags=self.tags,
            channels=self.channels,
            inferred_map=self.inferred_map,
            map_flags=self.map_flags,
            bundle=self.bundle,
        )

    @classmethod
    def from_resource(cls, resource: DiscoveredResource) -> DiscoveredSkill:
        """Create a :class:`DiscoveredSkill` from a
        :class:`DiscoveredResource`.

        Only valid when ``resource.resource_type == "skill"``.
        """
        if resource.resource_type != "skill":
            msg = (
                f"Cannot convert resource_type="
                f"{resource.resource_type!r} to DiscoveredSkill"
            )
            raise ValueError(msg)
        canonical = CanonicalSkillId.from_str(resource.canonical_uri)
        return cls(
            canonical=canonical,
            title=resource.title,
            summary=resource.summary,
            original_author=resource.original_author,
            license_spdx=resource.license_spdx,
            source_commit=resource.source_commit,
            tags=resource.tags,
            channels=resource.channels,
            inferred_map=resource.inferred_map,
            map_flags=resource.map_flags,
            bundle=resource.bundle,
        )

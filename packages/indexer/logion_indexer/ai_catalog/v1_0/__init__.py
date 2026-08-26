# SPDX-License-Identifier: MIT
"""AI Catalog v1.0 models — frozen dataclasses for the typed catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from logion_indexer._json import JsonObject as JsonObject
from logion_indexer._json import JsonValue

ConformanceLevel = Literal["minimal", "discoverable", "trusted"]

#: Spec version string this module handles.
SPEC_VERSION = "1.0"

#: Media type for AI Catalog documents.
MEDIA_TYPE = "application/ai-catalog+json"

#: Known core protocol types (governed by the AI Catalog WG).
KNOWN_CORE_TYPES = frozenset({
    "application/ai-catalog+json",
    "application/agent-card+json",
})

#: Known integrated ecosystem types (governed externally).
KNOWN_ECOSYSTEM_TYPES = frozenset({
    "application/a2a-agent-card+json",
    "application/mcp-server-card+json",
    "application/agent-skills+json",
    "application/agent-skills+md",
    "application/agent-skills+zip",
    "application/agent-skills+gzip",
})

#: All recognized types (core + ecosystem).
KNOWN_TYPES = KNOWN_CORE_TYPES | KNOWN_ECOSYSTEM_TYPES


@dataclass(frozen=True)
class TrustSchema:
    """Trust Schema object within a Trust Manifest."""

    identifier: str
    version: str
    governance_uri: str | None = None
    verification_methods: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Attestation:
    """A verifiable proof of a claim."""

    type: str
    uri: str
    digest: str | None = None
    size: int | None = None
    description: str | None = None


@dataclass(frozen=True)
class ProvenanceLink:
    """A lineage relationship to another artifact or source."""

    relation: str
    source_id: str
    source_digest: str | None = None
    registry_uri: str | None = None
    statement_uri: str | None = None
    signature_ref: str | None = None


@dataclass(frozen=True)
class TrustManifest:
    """Verifiable identity, attestation, and provenance metadata."""

    identity: str
    identity_type: str | None = None
    trust_schema: TrustSchema | None = None
    attestations: tuple[Attestation, ...] = field(default_factory=tuple)
    provenance: tuple[ProvenanceLink, ...] = field(default_factory=tuple)
    privacy_policy_url: str | None = None
    terms_of_service_url: str | None = None
    signature: str | None = None


@dataclass(frozen=True)
class Publisher:
    """The entity responsible for publishing an artifact."""

    identifier: str
    display_name: str
    identity_type: str | None = None


@dataclass(frozen=True)
class HostInfo:
    """Operator of the catalog."""

    display_name: str
    identifier: str | None = None
    documentation_url: str | None = None
    logo_url: str | None = None
    trust_manifest: TrustManifest | None = None


@dataclass(frozen=True)
class CatalogEntry:
    """A single AI artifact entry in the catalog.

    Exactly one of ``url`` or ``data`` must be set (the spec's
    value-or-reference rule). Unknown optional fields are preserved
    in ``extra`` for forward-compatibility (must-ignore semantics).
    """

    identifier: str
    type: str
    url: str | None = None
    data: JsonValue | None = None
    display_name: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    version: str | None = None
    updated_at: str | None = None
    publisher: Publisher | None = None
    trust_manifest: TrustManifest | None = None
    #: ARD-specific optional fields (§4.2) — preserved but not
    #: part of the base AI Catalog spec. Kept separate so the AI
    #: Catalog codec stays spec-pure.
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    representative_queries: tuple[str, ...] = field(default_factory=tuple)
    #: Namespaced or unknown optional fields the codec must preserve
    #: but does not interpret.
    extra: tuple[tuple[str, JsonValue], ...] = field(default_factory=tuple)

    @property
    def is_nested_catalog(self) -> bool:
        """True when this entry's type is a nested AI Catalog."""
        return self.type == MEDIA_TYPE

    @property
    def is_registry(self) -> bool:
        """True when this entry references an ARD registry."""
        return self.type == "application/ai-registry+json"

    @property
    def display_or_fallback(self) -> str:
        """Resolve a display name per the spec's resolution order."""
        if self.display_name:
            return self.display_name
        return self.identifier.rsplit(":", 1)[-1].rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Catalog:
    """A parsed AI Catalog document (specVersion 1.0)."""

    spec_version: str
    entries: tuple[CatalogEntry, ...] = field(default_factory=tuple)
    host: HostInfo | None = None
    #: Namespaced or unknown top-level fields the codec must preserve.
    extra: tuple[tuple[str, JsonValue], ...] = field(default_factory=tuple)

    @property
    def conformance_level(self) -> ConformanceLevel:
        """Determine the conformance level of this catalog.

        - ``minimal``: valid catalog with entries.
        - ``discoverable``: served at a well-known URL (not determinable
          from the document alone; callers set this).
        - ``trusted``: at least one entry carries a Trust Manifest with
          a signature.
        """
        has_trust = any(
            e.trust_manifest and e.trust_manifest.signature
            for e in self.entries
        )
        if has_trust:
            return "trusted"
        return "minimal"

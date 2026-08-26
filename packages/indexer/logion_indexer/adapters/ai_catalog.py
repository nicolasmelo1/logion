# SPDX-License-Identifier: MIT
"""AI Catalog adapter: crawl an AI Catalog endpoint into DiscoveredResource.

The AI Catalog identifier (a ``urn:air:`` URN) maps to a Logion
:class:`DiscoveredResource` through an explicit source mapping. The
catalog's ``type`` field determines the ``resource_type``, and the
``identifier`` is carried as the canonical URI with the catalog
source URL recorded as a discovery channel.

Key constraints from the plan:
- A selection-descriptor digest must NOT create a ResourceVersion.
- Unknown artifact types are preserved (not rejected).
- Namespaced metadata is preserved in channel metadata.
- Relevance score is never trust/safety evidence (handled at the ARD
  layer; this adapter carries no scores).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..ai_catalog.v1_0 import (
    Catalog,
    CatalogEntry,
)
from ..ai_catalog.v1_0.codec import (
    ERROR_CODE_DOCUMENT_INVALID,
    ERROR_CODE_VERSION_UNSUPPORTED,
    AICatalogDecodeError,
    AICatalogVersionUnsupported,
    EntryRejection,
    decode_catalog_tolerant,
)
from ..canonical import CanonicalResourceId
from ..models import DiscoveredResource, DiscoveryChannel
from ..transport import Transport

#: Mapping from AI Catalog media types to Logion resource types.
_TYPE_MAP: dict[str, str] = {
    "application/agent-skills+json": "skill",
    "application/agent-skills+md": "skill",
    "application/agent-skills+zip": "skill",
    "application/agent-skills+gzip": "skill",
    "application/mcp-server-card+json": "mcp_server",
    "application/a2a-agent-card+json": "mcp_server",
    "application/agent-card+json": "mcp_server",
    "application/ai-catalog+json": "catalog",
    "application/ai-registry+json": "registry",
}

#: Default resource type for unknown media types.
_DEFAULT_RESOURCE_TYPE = "artifact"

#: Quarantine codes this adapter adds on top of the codec's. Decoding
#: proves an entry is well-formed; these two say it is well-formed and
#: still unusable, which is a different thing to tell an operator.
ERROR_CODE_IDENTITY_MISSING = "ai_catalog_entry_identity_missing"
ERROR_CODE_IDENTITY_INVALID = "ai_catalog_entry_identity_invalid"
ERROR_CODE_FETCH_FAILED = "ai_catalog_fetch_failed"


def _map_resource_type(media_type: str) -> str:
    """Map an AI Catalog media type to a Logion resource type.

    Unknown types are preserved as ``"artifact"`` — the catalog is
    artifact-agnostic and Logion must not reject entries it doesn't
    recognize.
    """
    return _TYPE_MAP.get(media_type, _DEFAULT_RESOURCE_TYPE)


def _map_canonical_uri(identifier: str, _source_url: str = "") -> str:
    """Map an AI Catalog identifier to a canonical URI.

    The identifier is a URN (e.g. ``urn:air:example.com:mcp:weather``).
    Logion uses it directly as the canonical URI, prefixed with the
    source mapping. The source URL is recorded separately in the
    discovery channel.
    """
    return f"air:{identifier}"


@dataclass
class CatalogCrawlResult:
    """Result of crawling an AI Catalog endpoint.

    Attributes:
        resources: Discovered resources from catalog entries.
        nested_catalogs: URLs of nested catalog entries to follow.
        registry_urls: URLs of ARD registry entries found.
        errors: Per-entry errors that did not stop the crawl.
        rejected: Entries quarantined with a stable code and reason.
        seen: Entries the document offered, importable or not.
        source_url: The URL the catalog was fetched from.
    """

    resources: list[DiscoveredResource] = field(default_factory=list)
    nested_catalogs: list[str] = field(default_factory=list)
    registry_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rejected: list[EntryRejection] = field(default_factory=list)
    seen: int = 0
    source_url: str = ""

    def quarantine(self, entry: EntryRejection) -> None:
        """Record a rejection in both views callers read.

        ``rejected`` is what an import report groups by code; ``errors``
        is the flat prose list older callers already print. Writing one
        without the other is how a quarantined entry becomes invisible
        to half the code that looks for it.
        """
        self.rejected.append(entry)
        named = f"entry {entry.identifier!r}: " if entry.identifier else ""
        self.errors.append(f"{named}{entry.reason} [{entry.error_code}]")

    @property
    def errors_by_code(self) -> dict[str, int]:
        """Count quarantined entries by stable code."""
        counts: dict[str, int] = {}
        for entry in self.rejected:
            counts[entry.error_code] = counts.get(entry.error_code, 0) + 1
        return counts


class AICatalogAdapter:
    """Discover resources from an AI Catalog endpoint.

    Fetches the catalog at the given entrypoint URL, parses it through
    the v1.0 codec, and yields :class:`DiscoveredResource` objects for
    each entry. Nested catalogs (``application/ai-catalog+json``) are
    collected for recursive crawling but not followed automatically;
    the caller decides whether to recurse.
    """

    hub_slug = "ai-catalog"

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
    ) -> Iterable[DiscoveredResource]:
        """Discover resources from an AI Catalog URL.

        Args:
            target: URL of the AI Catalog document.
            limit: Maximum number of resources to yield.
        """
        result = self.crawl(target, limit=limit)
        yield from result.resources

    def crawl(
        self,
        entrypoint_url: str,
        *,
        limit: int | None = None,
    ) -> CatalogCrawlResult:
        """Crawl a single AI Catalog endpoint.

        Returns a :class:`CatalogCrawlResult` with resources, nested
        catalog URLs, and any per-entry errors.
        """
        result = CatalogCrawlResult(source_url=entrypoint_url)

        resp = self.transport.get(entrypoint_url)
        if resp.status != 200:
            result.quarantine(
                EntryRejection(
                    identifier="",
                    error_code=ERROR_CODE_FETCH_FAILED,
                    reason=(
                        f"fetch failed: {entrypoint_url} -> HTTP {resp.status}"
                    ),
                )
            )
            return result

        catalog = self._decode_catalog_response(resp, result)
        if catalog is None:
            return result

        self._collect_entries(catalog, entrypoint_url, limit, result)
        return result

    @staticmethod
    def _decode_catalog_response(
        resp: object,
        result: CatalogCrawlResult,
    ) -> Catalog | None:
        """Parse and decode the fetched response body into a Catalog.

        Appends any fetch/decode error to ``result.errors`` and returns
        ``None`` so the caller can short-circuit.
        """
        try:
            doc = json.loads(resp.body.decode("utf-8"))  # type: ignore[attr-defined]
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            result.quarantine(
                EntryRejection(
                    identifier="",
                    error_code=ERROR_CODE_DOCUMENT_INVALID,
                    reason=f"invalid JSON: {e}",
                )
            )
            return None

        try:
            catalog, rejected = decode_catalog_tolerant(doc)
        except AICatalogVersionUnsupported as e:
            result.quarantine(
                EntryRejection(
                    identifier="",
                    error_code=ERROR_CODE_VERSION_UNSUPPORTED,
                    reason=str(e),
                )
            )
            return None
        except AICatalogDecodeError as e:
            result.quarantine(
                EntryRejection(
                    identifier="",
                    error_code=ERROR_CODE_DOCUMENT_INVALID,
                    reason=str(e),
                )
            )
            return None
        for entry in rejected:
            result.quarantine(entry)
        result.seen += len(rejected)
        return catalog

    def _collect_entries(
        self,
        catalog: Catalog,
        entrypoint_url: str,
        limit: int | None,
        result: CatalogCrawlResult,
    ) -> None:
        """Walk catalog entries, populating ``result`` in place."""
        count = 0
        result.seen += len(catalog.entries)
        for entry in catalog.entries:
            if limit is not None and count >= limit:
                break

            if entry.is_nested_catalog:
                if entry.url:
                    result.nested_catalogs.append(entry.url)
                # Nested catalogs via `data` are not followed
                # automatically; the caller may parse them.
                continue

            if entry.is_registry and entry.url:
                result.registry_urls.append(entry.url)

            resource = self._entry_to_resource(entry, entrypoint_url, catalog)
            if resource is None:
                result.quarantine(self._identity_rejection(entry))
                continue
            result.resources.append(resource)
            count += 1

    @staticmethod
    def _identity_rejection(entry: CatalogEntry) -> EntryRejection:
        """Say which half of identity an unusable entry was missing.

        A decoded entry that still cannot become a resource failed on
        identity, and the operator's next move differs by which half:
        a missing identifier is the publisher's to fix, an unmappable
        one may be ours.
        """
        if not entry.identifier or not entry.type:
            return EntryRejection(
                identifier=entry.identifier,
                error_code=ERROR_CODE_IDENTITY_MISSING,
                reason="entry has no identifier or no type",
            )
        return EntryRejection(
            identifier=entry.identifier,
            error_code=ERROR_CODE_IDENTITY_INVALID,
            reason=(
                f"identifier does not map to a canonical resource id: "
                f"{entry.identifier!r}"
            ),
        )

    @staticmethod
    def _entry_to_resource(
        entry: CatalogEntry,
        source_url: str,
        catalog: Catalog,  # noqa: ARG004
    ) -> DiscoveredResource | None:
        """Convert a catalog entry to a DiscoveredResource.

        The AI Catalog identifier maps to Resource through an explicit
        source mapping. A selection-descriptor digest must NOT create
        a ResourceVersion, so no digest is computed here.
        """
        if not entry.identifier or not entry.type:
            return None

        resource_type = _map_resource_type(entry.type)
        canonical_uri = _map_canonical_uri(entry.identifier, source_url)

        try:
            canonical = CanonicalResourceId(
                resource_type=resource_type,
                uri=canonical_uri,
            )
        except ValueError:
            return None

        # Collect namespaced metadata from the entry's extra fields.
        metadata: list[tuple[str, str]] = []
        # The entry's own word for what it is. A Logion resource type and
        # an AI Catalog media type are different vocabularies, and the
        # mapping between them is lossy in one direction: `skill` cannot
        # say whether the catalog called it +json or +zip. Keeping the
        # original is what lets a re-crawl of our own catalog recover the
        # type the entry started with instead of a normalized guess.
        metadata.append(("ai_catalog_type", entry.type))
        for key, value in entry.extra:
            metadata.append((key, str(value)))

        channel = DiscoveryChannel(
            hub_slug="ai-catalog",
            hub_url=source_url,
            hub_verified=False,
            metadata=tuple(metadata),
        )

        return DiscoveredResource(
            canonical=canonical,
            resource_type=resource_type,
            canonical_uri=canonical_uri,
            title=entry.display_or_fallback,
            summary=entry.description or "",
            original_author=_extract_publisher(entry),
            license_spdx=None,
            source_commit=None,
            tags=entry.tags,
            channels=(channel,),
            declared_capabilities=(
                {"capabilities": list(entry.capabilities)}
                if entry.capabilities
                else None
            ),
        )


def _extract_publisher(entry: CatalogEntry) -> str:
    """Extract the publisher name from an entry, if present."""
    if entry.publisher and entry.publisher.display_name:
        return entry.publisher.display_name
    # Try to extract from the URN identifier.
    parts = entry.identifier.split(":")
    if len(parts) >= 3:
        return parts[2]
    return ""


__all__ = [
    "ERROR_CODE_FETCH_FAILED",
    "ERROR_CODE_IDENTITY_INVALID",
    "ERROR_CODE_IDENTITY_MISSING",
    "AICatalogAdapter",
    "CatalogCrawlResult",
]

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
    AICatalogDecodeError,
    AICatalogVersionUnsupported,
    decode_catalog,
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
        source_url: The URL the catalog was fetched from.
    """

    resources: list[DiscoveredResource] = field(default_factory=list)
    nested_catalogs: list[str] = field(default_factory=list)
    registry_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_url: str = ""


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
            result.errors.append(
                f"fetch failed: {entrypoint_url} -> HTTP {resp.status}"
            )
            return result

        try:
            doc = json.loads(resp.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            result.errors.append(f"invalid JSON: {e}")
            return result

        try:
            catalog = decode_catalog(doc)
        except AICatalogVersionUnsupported as e:
            result.errors.append(str(e))
            return result
        except AICatalogDecodeError as e:
            result.errors.append(str(e))
            return result

        count = 0
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
                # Registry entries are still discoverable as resources.
                resource = self._entry_to_resource(
                    entry, entrypoint_url, catalog
                )
                if resource is not None:
                    result.resources.append(resource)
                    count += 1
                continue

            resource = self._entry_to_resource(entry, entrypoint_url, catalog)
            if resource is not None:
                result.resources.append(resource)
                count += 1

        return result

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
    "AICatalogAdapter",
    "CatalogCrawlResult",
]

# SPDX-License-Identifier: MIT
"""ARD adapter: search an ARD registry and yield DiscoveredResource.

The ARD adapter uses the :class:`ARDClient` to perform POST /search
against a registry, then converts the returned catalog entries into
:class:`DiscoveredResource` objects through the same source mapping
as the AI Catalog adapter.

Key constraints:
- Relevance score is never trust/safety evidence — it is carried in
  channel metadata as ``relevance_score`` but never in a Logion
  evidence field.
- The ARD adapter does not install connector files or finder
  preferences into customer clients.
- ARD and AI Catalog have separate error codes: ``ard_version_unsupported``
  vs ``ai_catalog_version_unsupported``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..ard.v0_9 import SearchFilter, SearchQuery, SearchRequest, SearchResult
from ..ard.v0_9.client import ARDClient
from ..ard.v0_9.codec import ARDDecodeError
from ..canonical import CanonicalResourceId
from ..models import DiscoveredResource, DiscoveryChannel
from ..transport import Transport
from .ai_catalog import _map_resource_type


@dataclass
class ARDSearchResult:
    """Result of an ARD search operation.

    Attributes:
        resources: Discovered resources from search results.
        referrals: Referral registry URLs for federation.
        errors: Errors encountered during search.
        page_token: Pagination token for the next page, if any.
    """

    resources: list[DiscoveredResource] = field(default_factory=list)
    referrals: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    page_token: str | None = None


class ARDAdapter:
    """Discover resources from an ARD registry via POST /search.

    This adapter searches a registry and converts results into
    :class:`DiscoveredResource` objects. It uses the same type mapping
    as the AI Catalog adapter so resources discovered through either
    path converge on the same canonical identity.
    """

    hub_slug = "ard"

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
        query_text: str = "",
    ) -> Iterable[DiscoveredResource]:
        """Discover resources from an ARD registry.

        Args:
            target: Base URL of the ARD registry.
            limit: Maximum results per page.
            query_text: Natural-language search query.
        """
        result = self.search(
            target,
            query_text=query_text,
            page_size=limit or 10,
        )
        yield from result.resources

    def search(
        self,
        registry_url: str,
        *,
        query_text: str = "",
        filter_: SearchFilter | None = None,
        federation: str = "auto",
        page_size: int = 10,
        page_token: str | None = None,
    ) -> ARDSearchResult:
        """Execute a search against an ARD registry."""
        result = ARDSearchResult()
        client = ARDClient(self.transport, registry_url)

        search_query = SearchQuery(
            text=query_text if query_text else None,
            filter=filter_ or SearchFilter(),
        )
        request = SearchRequest(
            query=search_query,
            federation=federation,  # type: ignore[arg-type]
            page_size=min(page_size, 100),
            page_token=page_token,
        )

        try:
            response = client.search(request)
        except ARDDecodeError as e:
            result.errors.append(str(e))
            return result

        result.page_token = response.page_token

        for referral in response.referrals:
            if referral.url:
                result.referrals.append(referral.url)

        for search_result in response.results:
            resource = self._result_to_resource(search_result, registry_url)
            if resource is not None:
                result.resources.append(resource)

        return result

    @staticmethod
    def _result_to_resource(
        result: SearchResult,
        registry_url: str,
    ) -> DiscoveredResource | None:
        """Convert an ARD search result to a DiscoveredResource.

        Relevance score is recorded in channel metadata as
        ``relevance_score`` — it is never trust/safety evidence.
        """
        if not result.identifier or not result.type:
            return None

        resource_type = _map_resource_type(result.type)
        canonical_uri = f"air:{result.identifier}"

        try:
            canonical = CanonicalResourceId(
                resource_type=resource_type,
                uri=canonical_uri,
            )
        except ValueError:
            return None

        # Build channel metadata: relevance score (not evidence),
        # source registry, and any extra fields.
        metadata: list[tuple[str, str]] = []
        if result.score is not None:
            metadata.append(("relevance_score", str(result.score)))
        if result.source is not None:
            metadata.append(("ard_source", result.source))
        for key, value in result.extra:
            metadata.append((key, str(value)))

        channel = DiscoveryChannel(
            hub_slug="ard",
            hub_url=registry_url,
            hub_verified=False,
            metadata=tuple(metadata),
        )

        # Construct a minimal CatalogEntry-like object for publisher
        # extraction. We use a simple object to avoid importing the
        # full dataclass.
        publisher_name = ""
        # Try to extract publisher from the URN identifier.
        parts = result.identifier.split(":")
        if len(parts) >= 3:
            publisher_name = parts[2]

        return DiscoveredResource(
            canonical=canonical,
            resource_type=resource_type,
            canonical_uri=canonical_uri,
            title=result.display_name or result.identifier.rsplit(":", 1)[-1],
            summary="",
            original_author=publisher_name,
            license_spdx=None,
            source_commit=None,
            tags=(),
            channels=(channel,),
            declared_capabilities=(
                {"capabilities": list(result.capabilities)}
                if result.capabilities
                else None
            ),
        )


__all__ = [
    "ARDAdapter",
    "ARDSearchResult",
]

# SPDX-License-Identifier: MIT
"""Agent Finders source: bounded multi-finder scheduling and query.

For each enabled finder from a pinned :class:`AgentFindersSnapshot`,
this module queries the finder's search endpoint using the upstream
canonical request format, records discovery provenance, and normalizes
results into :class:`DiscoveredResource` objects.

CRITICAL constraints:
- Relevance score is never trust/safety evidence — it is recorded in
  channel metadata only.
- No connector files or finder preferences are installed into customer
  clients.
- Finder auth, if later supported, uses operator-managed secret
  references outside the snapshot.
- Referral candidates are recorded as untrusted; query only after
  endpoint validation and operator approval.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import cast

from logion_indexer._json import JsonObject, JsonValue
from logion_indexer.ard.v0_9 import (
    SearchFilter,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from logion_indexer.ard.v0_9.codec import decode_search_response
from logion_indexer.canonical import CanonicalResourceId
from logion_indexer.models import DiscoveredResource, DiscoveryChannel
from logion_indexer.transport import Transport

from ..adapters.ai_catalog import _map_resource_type
from .ard_connectors import AgentFindersSnapshot, FinderEntry


@dataclass(frozen=True)
class FinderQueryRecord:
    """Provenance record for a single finder query.

    Records everything the plan requires: finder ID, endpoint, snapshot
    commit/digest, query text digest, filters, retrieval time, referrals,
    raw result digest, relevance score, and returned entry identity.
    """

    finder_id: str
    endpoint: str
    snapshot_commit: str
    snapshot_digest: str
    query_text: str
    query_text_digest: str
    filters: tuple[tuple[str, list[str]], ...]
    retrieved_at: float
    raw_result_digest: str
    result_identifiers: tuple[str, ...]
    referral_urls: tuple[str, ...]
    relevance_scores: tuple[tuple[str, int], ...]
    error: str | None = None


@dataclass
class FinderRunResult:
    """Result of running queries against all enabled finders.

    Attributes:
        resources: All discovered resources across finders.
        records: Per-query provenance records.
        referrals: Untrusted referral candidate URLs.
        errors: Per-finder errors.
    """

    resources: list[DiscoveredResource] = field(default_factory=list)
    records: list[FinderQueryRecord] = field(default_factory=list)
    referrals: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class AgentFindersSource:
    """Query enabled Agent Finders and normalize results.

    This is an indexer control-plane source. It does NOT install
    connector files or finder preferences into customer clients.
    """

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def run(
        self,
        snapshot: AgentFindersSnapshot,
        *,
        query_text: str = "",
        resource_types: list[str] | None = None,
        max_results: int = 100,
        approved_finder_ids: set[str] | None = None,
    ) -> FinderRunResult:
        """Query all enabled (and approved) finders in a snapshot.

        Args:
            snapshot: Pinned agent-finders snapshot.
            query_text: Bounded discovery query.
            resource_types: Optional filter on AI Catalog media types.
            max_results: Maximum total results across all finders.
            approved_finder_ids: Only query finders whose IDs are in
                this set. If None, all finders in the snapshot are
                queried (subject to operator approval elsewhere).
        """
        result = FinderRunResult()
        total = 0

        for finder in snapshot.finders:
            if (
                approved_finder_ids is not None
                and finder.id not in approved_finder_ids
            ):
                continue
            if not finder.search:
                continue
            if total >= max_results:
                break

            record, resources, referrals = self._query_finder(
                finder=finder,
                snapshot=snapshot,
                query_text=query_text,
                resource_types=resource_types,
                remaining=max_results - total,
            )

            result.records.append(record)
            result.referrals.extend(referrals)
            if record.error:
                result.errors.append(record.error)
            result.resources.extend(resources)
            total += len(resources)

        return result

    def _query_finder(
        self,
        *,
        finder: FinderEntry,
        snapshot: AgentFindersSnapshot,
        query_text: str,
        resource_types: list[str] | None,
        remaining: int,
    ) -> tuple[FinderQueryRecord, list[DiscoveredResource], list[str]]:
        """Query a single finder and return (record, resources, referrals)."""
        filters = self._build_filters(resource_types)
        query = SearchQuery(
            text=query_text if query_text else None,
            filter=SearchFilter(constraints=filters),
        )

        request_body = self._build_request_body(query)
        query_text_digest = hashlib.sha256(
            query_text.encode("utf-8")
        ).hexdigest()

        resp = self.transport.post(
            finder.search,
            json_body=request_body,
            headers={"Content-Type": "application/json"},
        )

        retrieved_at = time.time()

        if resp.status != 200:
            error = f"finder {finder.id!r}: search failed: HTTP {resp.status}"
            record = self._error_record(
                finder,
                snapshot,
                query_text,
                query_text_digest,
                filters,
                retrieved_at,
                error,
            )
            return (record, [], [])

        raw_digest = hashlib.sha256(resp.body).hexdigest()

        try:
            search_response = decode_search_response(
                cast(JsonValue, resp.json())
            )
        except Exception as e:
            error = f"finder {finder.id!r}: decode error: {e}"
            record = self._error_record(
                finder,
                snapshot,
                query_text,
                query_text_digest,
                filters,
                retrieved_at,
                error,
                raw_digest,
            )
            return (record, [], [])

        resources, identifiers, scores, referrals = self._collect_results(
            search_response,
            finder,
            snapshot,
            remaining,
        )

        record = FinderQueryRecord(
            finder_id=finder.id,
            endpoint=finder.search,
            snapshot_commit=snapshot.commit_sha,
            snapshot_digest=snapshot.file_digest,
            query_text=query_text,
            query_text_digest=query_text_digest,
            filters=tuple(filters.items()),
            retrieved_at=retrieved_at,
            raw_result_digest=raw_digest,
            result_identifiers=tuple(identifiers),
            referral_urls=tuple(referrals),
            relevance_scores=tuple(scores),
        )

        return (record, resources, referrals)

    @staticmethod
    def _build_filters(
        resource_types: list[str] | None,
    ) -> dict[str, list[str]]:
        """Build the ARD filter dict from optional resource types."""
        filters: dict[str, list[str]] = {}
        if resource_types:
            filters["type"] = resource_types
        return filters

    @staticmethod
    def _build_request_body(query: SearchQuery) -> JsonObject:
        """Build the upstream canonical request body."""
        request_body: JsonObject = {"query": {}}
        if query.text:
            request_body["query"]["text"] = query.text  # type: ignore[index]
        if query.filter.constraints:
            request_body["query"]["filter"] = (  # type: ignore[index]
                query.filter.to_json()
            )
        return request_body

    @staticmethod
    def _error_record(
        finder: FinderEntry,
        snapshot: AgentFindersSnapshot,
        query_text: str,
        query_text_digest: str,
        filters: dict[str, list[str]],
        retrieved_at: float,
        error: str,
        raw_digest: str = "",
    ) -> FinderQueryRecord:
        """Construct a provenance record for a failed finder query."""
        return FinderQueryRecord(
            finder_id=finder.id,
            endpoint=finder.search,
            snapshot_commit=snapshot.commit_sha,
            snapshot_digest=snapshot.file_digest,
            query_text=query_text,
            query_text_digest=query_text_digest,
            filters=tuple(filters.items()),
            retrieved_at=retrieved_at,
            raw_result_digest=raw_digest,
            result_identifiers=(),
            referral_urls=(),
            relevance_scores=(),
            error=error,
        )

    def _collect_results(
        self,
        search_response: SearchResponse,
        finder: FinderEntry,
        snapshot: AgentFindersSnapshot,
        remaining: int,
    ) -> tuple[
        list[DiscoveredResource],
        list[str],
        list[tuple[str, int]],
        list[str],
    ]:
        """Collect resources, identifiers, scores, and referrals."""
        resources: list[DiscoveredResource] = []
        identifiers: list[str] = []
        scores: list[tuple[str, int]] = []
        referrals: list[str] = []

        for referral in search_response.referrals:
            if referral.url:
                referrals.append(referral.url)

        for sr in search_response.results:
            if len(resources) >= remaining:
                break
            resource = self._result_to_resource(sr, finder, snapshot)
            if resource is not None:
                resources.append(resource)
                identifiers.append(sr.identifier)
                if sr.score is not None:
                    scores.append((sr.identifier, sr.score))

        return (resources, identifiers, scores, referrals)

    @staticmethod
    def _result_to_resource(
        result: SearchResult,
        finder: FinderEntry,
        snapshot: AgentFindersSnapshot,
    ) -> DiscoveredResource | None:
        """Convert a finder search result to a DiscoveredResource.

        Relevance score is carried in channel metadata — it is never
        trust/safety evidence.
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

        metadata: list[tuple[str, str]] = [
            ("finder_id", finder.id),
            ("finder_name", finder.name),
            ("snapshot_commit", snapshot.commit_sha),
        ]
        if result.score is not None:
            metadata.append(("relevance_score", str(result.score)))
        if result.source is not None:
            metadata.append(("ard_source", result.source))

        channel = DiscoveryChannel(
            hub_slug="agent-finder",
            hub_url=finder.search,
            hub_verified=False,
            metadata=tuple(metadata),
        )

        parts = result.identifier.split(":")
        publisher = parts[2] if len(parts) >= 3 else ""

        return DiscoveredResource(
            canonical=canonical,
            resource_type=resource_type,
            canonical_uri=canonical_uri,
            title=result.display_name or result.identifier.rsplit(":", 1)[-1],
            summary="",
            original_author=publisher,
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
    "AgentFindersSource",
    "FinderQueryRecord",
    "FinderRunResult",
]

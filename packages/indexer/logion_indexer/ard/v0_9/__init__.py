# SPDX-License-Identifier: MIT
"""ARD v0.9 models — frozen dataclasses for search/explore/federation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from logion_indexer._json import JsonObject, JsonValue

#: ARD spec version this module handles.
SPEC_VERSION = "0.9"

#: Media type for ARD registry entries.
REGISTRY_MEDIA_TYPE = "application/ai-registry+json"

#: Federation modes.
FederationMode = Literal["auto", "referrals", "none"]


@dataclass(frozen=True)
class SearchFilter:
    """Structured constraints for a search/explore query.

    Keys are dot-separated field paths into the catalog entry;
    values are arrays (OR within a key, AND across keys).
    """

    constraints: dict[str, list[str]] = field(default_factory=dict)

    def to_json(self) -> JsonObject:
        return {k: list(v) for k, v in self.constraints.items()}

    @classmethod
    def from_json(cls, obj: JsonObject | None) -> SearchFilter:
        if obj is None:
            return cls()
        constraints: dict[str, list[str]] = {}
        for key, value in obj.items():
            if isinstance(value, list):
                constraints[key] = [
                    str(v) for v in value if isinstance(v, str)
                ]
            elif isinstance(value, str):
                constraints[key] = [value]
        return cls(constraints=constraints)


@dataclass(frozen=True)
class SearchQuery:
    """The common query object for search and explore."""

    text: str | None = None
    filter: SearchFilter = field(default_factory=SearchFilter)


@dataclass(frozen=True)
class SearchRequest:
    """POST /search request body."""

    query: SearchQuery
    federation: FederationMode = "auto"
    page_size: int = 10
    page_token: str | None = None


@dataclass(frozen=True)
class SearchResult:
    """A single result in a search response.

    The ``score`` field is a registry-supplied relevance metric
    (0-100). It is strictly informational and MUST NOT be interpreted
    as trust, compliance, or safety evidence.
    """

    identifier: str
    type: str
    url: str | None = None
    data: JsonValue | None = None
    display_name: str | None = None
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    score: int | None = None
    source: str | None = None
    #: Unknown optional fields preserved per must-ignore rules.
    extra: tuple[tuple[str, JsonValue], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Referral:
    """A referral to another registry."""

    identifier: str
    display_name: str | None = None
    type: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class SearchResponse:
    """POST /search response."""

    results: tuple[SearchResult, ...] = field(default_factory=tuple)
    referrals: tuple[Referral, ...] = field(default_factory=tuple)
    page_token: str | None = None


@dataclass(frozen=True)
class FacetBucket:
    """A single bucket in a facet aggregation."""

    value: str
    count: int | None = None


@dataclass(frozen=True)
class Facet:
    """A facet aggregation over a field path."""

    field_name: str
    buckets: tuple[FacetBucket, ...] = field(default_factory=tuple)
    other_count: int | None = None


@dataclass(frozen=True)
class ExploreRequest:
    """POST /explore request body."""

    query: SearchQuery
    facets: tuple[str, ...] = field(default_factory=tuple)
    facet_limits: dict[str, int] = field(default_factory=dict)
    facet_min_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ExploreResponse:
    """POST /explore response."""

    facets: tuple[Facet, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ARDError:
    """An ARD error from the standard error codes table."""

    code: str
    message: str
    http_status: int | None = None


#: Standard ARD error codes (Appendix B).
ARD_ERROR_CODES = frozenset({
    "INVALID_ARGUMENT",
    "UNAUTHENTICATED",
    "NOT_FOUND",
    "RATE_LIMIT_EXCEEDED",
    "INTERNAL_ERROR",
})

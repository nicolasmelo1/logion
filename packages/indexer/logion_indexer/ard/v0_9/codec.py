# SPDX-License-Identifier: MIT
"""ARD v0.9 codec: decode/encode search/explore JSON ↔ dataclasses."""

from __future__ import annotations

from logion_indexer._json import (
    JsonObject,
    JsonValue,
    as_object,
    opt_int,
    opt_object,
    opt_str,
    opt_str_array,
    require_str,
)

from . import (
    ExploreRequest,
    ExploreResponse,
    Facet,
    FacetBucket,
    Referral,
    SearchRequest,
    SearchResponse,
    SearchResult,
)

#: Known keys on a search result entry.
_RESULT_KNOWN_KEYS = frozenset({
    "identifier",
    "type",
    "url",
    "data",
    "displayName",
    "capabilities",
    "score",
    "source",
    "description",
    "tags",
    "version",
    "updatedAt",
    "metadata",
    "trustManifest",
    "representativeQueries",
})


class ARDVersionUnsupported(ValueError):
    """The ARD response version is not supported by this codec."""

    error_code = "ard_version_unsupported"


class ARDDecodeError(ValueError):
    """An ARD document failed structural validation."""


def encode_search_request(req: SearchRequest) -> JsonObject:
    """Encode a :class:`SearchRequest` to JSON for POST /search."""
    query: JsonObject = {}
    if req.query.text is not None:
        query["text"] = req.query.text
    if req.query.filter.constraints:
        query["filter"] = req.query.filter.to_json()
    result: JsonObject = {"query": query}
    if req.federation != "auto":
        result["federation"] = req.federation
    if req.page_size != 10:
        result["pageSize"] = req.page_size
    if req.page_token is not None:
        result["pageToken"] = req.page_token
    return result


def decode_search_response(doc: JsonValue) -> SearchResponse:
    """Decode a POST /search response into :class:`SearchResponse`."""
    obj = as_object(doc, where="ard search response")

    results: list[SearchResult] = []
    results_raw = obj.get("results")
    if isinstance(results_raw, list):
        for item in results_raw:
            if isinstance(item, dict):
                results.append(_decode_result(item))

    referrals: list[Referral] = []
    referrals_raw = obj.get("referrals")
    if isinstance(referrals_raw, list):
        for item in referrals_raw:
            if isinstance(item, dict):
                referrals.append(_decode_referral(item))

    page_token = opt_str(obj, "pageToken")

    return SearchResponse(
        results=tuple(results),
        referrals=tuple(referrals),
        page_token=page_token,
    )


def encode_explore_request(req: ExploreRequest) -> JsonObject:
    """Encode an :class:`ExploreRequest` to JSON for POST /explore."""
    query: JsonObject = {}
    if req.query.text is not None:
        query["text"] = req.query.text
    if req.query.filter.constraints:
        query["filter"] = req.query.filter.to_json()
    facets: list[JsonObject] = []
    for f in req.facets:
        facet_obj: JsonObject = {"field": f}
        if f in req.facet_limits:
            facet_obj["limit"] = req.facet_limits[f]
        if f in req.facet_min_counts:
            facet_obj["minCount"] = req.facet_min_counts[f]
        facets.append(facet_obj)
    return {
        "query": query,
        "resultType": {"facets": facets},
    }


def decode_explore_response(doc: JsonValue) -> ExploreResponse:
    """Decode a POST /explore response into :class:`ExploreResponse`."""
    obj = as_object(doc, where="ard explore response")
    facets: list[Facet] = []
    facets_raw = opt_object(obj, "facets")
    if facets_raw is not None:
        for field_name, facet_data in facets_raw.items():
            if not isinstance(facet_data, dict):
                continue
            buckets: list[FacetBucket] = []
            buckets_raw = facet_data.get("buckets")
            if isinstance(buckets_raw, list):
                for bucket in buckets_raw:
                    if not isinstance(bucket, dict):
                        continue
                    value = opt_str(bucket, "value")
                    if value is None:
                        continue
                    count = opt_int(bucket, "count")
                    buckets.append(FacetBucket(value=value, count=count))
            other_count = opt_int(facet_data, "otherCount")
            facets.append(
                Facet(
                    field_name=field_name,
                    buckets=tuple(buckets),
                    other_count=other_count,
                )
            )
    return ExploreResponse(facets=tuple(facets))


def _decode_result(obj: JsonObject) -> SearchResult:
    identifier = require_str(obj, "identifier")
    entry_type = require_str(obj, "type")
    url = opt_str(obj, "url")
    data = obj.get("data")
    display_name = opt_str(obj, "displayName")
    capabilities = tuple(opt_str_array(obj, "capabilities"))
    score = opt_int(obj, "score")
    source = opt_str(obj, "source")
    extra = tuple(
        (key, obj[key]) for key in sorted(obj) if key not in _RESULT_KNOWN_KEYS
    )
    return SearchResult(
        identifier=identifier,
        type=entry_type,
        url=url,
        data=data,
        display_name=display_name,
        capabilities=capabilities,
        score=score,
        source=source,
        extra=extra,
    )


def _decode_referral(obj: JsonObject) -> Referral:
    identifier = require_str(obj, "identifier")
    display_name = opt_str(obj, "displayName")
    entry_type = opt_str(obj, "type")
    url = opt_str(obj, "url")
    return Referral(
        identifier=identifier,
        display_name=display_name,
        type=entry_type,
        url=url,
    )


__all__ = [
    "ARDDecodeError",
    "ARDVersionUnsupported",
    "decode_explore_response",
    "decode_search_response",
    "encode_explore_request",
    "encode_search_request",
]

# SPDX-License-Identifier: MIT
"""Tests for the ARD v0.9 codec, client, and models."""

from __future__ import annotations

import pytest

from logion_indexer.ard.v0_9 import (
    ExploreRequest,
    SearchFilter,
    SearchQuery,
    SearchRequest,
)
from logion_indexer.ard.v0_9.client import ARDClient
from logion_indexer.ard.v0_9.codec import (
    ARDDecodeError,
    decode_explore_response,
    decode_search_response,
    encode_explore_request,
    encode_search_request,
)
from logion_indexer.transport import FakeTransport, HttpResponse

SEARCH_RESPONSE = {
    "results": [
        {
            "identifier": "urn:air:acme.com:agent:assistant",
            "displayName": "Corporate Assistant",
            "type": "application/a2a-agent-card+json",
            "url": "https://api.acme.com/agents/assistant.json",
            "score": 95,
            "source": "https://registry.acme.com/api/v1/",
        },
        {
            "identifier": "urn:air:example.com:mcp:weather",
            "displayName": "Weather Service",
            "type": "application/mcp-server-card+json",
            "url": "https://weather.example.com/mcp",
            "capabilities": ["WeatherTool"],
            "score": 88,
        },
    ],
    "referrals": [
        {
            "identifier": "urn:air:nlweb.ai:registry:public",
            "displayName": "Public Agent Finder",
            "type": "application/ai-registry+json",
            "url": "https://finder.nlweb.ai/search",
        }
    ],
    "pageToken": "next=",
}


def test_decode_search_response() -> None:
    resp = decode_search_response(SEARCH_RESPONSE)
    assert len(resp.results) == 2
    assert resp.results[0].identifier == "urn:air:acme.com:agent:assistant"
    assert resp.results[0].score == 95
    assert resp.results[0].source == "https://registry.acme.com/api/v1/"
    assert resp.results[1].capabilities == ("WeatherTool",)
    assert len(resp.referrals) == 1
    assert resp.referrals[0].url == "https://finder.nlweb.ai/search"
    assert resp.page_token == "next="


def test_encode_search_request() -> None:
    req = SearchRequest(
        query=SearchQuery(
            text="find a weather agent",
            filter=SearchFilter(
                constraints={"type": ["application/mcp-server-card+json"]}
            ),
        ),
        federation="referrals",
        page_size=5,
    )
    encoded = encode_search_request(req)
    query = encoded["query"]
    assert isinstance(query, dict)
    assert query["text"] == "find a weather agent"
    filt = query["filter"]
    assert isinstance(filt, dict)
    assert filt["type"] == ["application/mcp-server-card+json"]
    assert encoded["federation"] == "referrals"
    assert encoded["pageSize"] == 5


def test_encode_search_request_defaults() -> None:
    req = SearchRequest(
        query=SearchQuery(text="test"),
    )
    encoded = encode_search_request(req)
    # federation=auto and pageSize=10 are defaults, should be omitted.
    assert "federation" not in encoded
    assert "pageSize" not in encoded


def test_search_response_with_extra_fields() -> None:
    doc = {
        "results": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "url": "https://example.com",
                "x-custom": "value",
            }
        ],
    }
    resp = decode_search_response(doc)
    extra_keys = [k for k, _ in resp.results[0].extra]
    assert "x-custom" in extra_keys


def test_explore_encode_decode() -> None:
    req = ExploreRequest(
        query=SearchQuery(text="currency"),
        facets=("type", "publisher"),
        facet_limits={"publisher": 50},
    )
    encoded = encode_explore_request(req)
    assert encoded["resultType"]["facets"][0]["field"] == "type"
    assert encoded["resultType"]["facets"][1]["limit"] == 50

    explore_resp = {
        "resultType": "facets",
        "facets": {
            "type": {
                "buckets": [
                    {
                        "value": "application/mcp-server-card+json",
                        "count": 1247,
                    },
                ],
                "otherCount": 23,
            },
        },
    }
    resp = decode_explore_response(explore_resp)
    assert len(resp.facets) == 1
    assert resp.facets[0].field_name == "type"
    assert resp.facets[0].buckets[0].count == 1247
    assert resp.facets[0].other_count == 23


def test_ard_client_search() -> None:
    transport = FakeTransport()
    registry = "https://registry.example.com"
    transport.set_post_response(
        f"{registry}/search",
        HttpResponse(200, b'{"results":[],"referrals":[]}'),
    )
    client = ARDClient(transport, registry)
    req = SearchRequest(query=SearchQuery(text="test"))
    resp = client.search(req)
    assert len(resp.results) == 0


def test_ard_client_search_error() -> None:
    transport = FakeTransport()
    registry = "https://registry.example.com"
    transport.set_post_response(
        f"{registry}/search",
        HttpResponse(
            400,
            b'{"code":"INVALID_ARGUMENT","message":"bad query"}',
        ),
    )
    client = ARDClient(transport, registry)
    req = SearchRequest(query=SearchQuery(text="test"))
    with pytest.raises(ARDDecodeError, match="INVALID_ARGUMENT"):
        client.search(req)


def test_ard_version_unsupported_error_code() -> None:
    from logion_indexer.ard.v0_9.codec import ARDVersionUnsupported

    assert ARDVersionUnsupported.error_code == "ard_version_unsupported"


def test_ai_catalog_version_unsupported_error_code() -> None:
    from logion_indexer.ai_catalog.v1_0.codec import (
        AICatalogVersionUnsupported,
    )

    assert (
        AICatalogVersionUnsupported.error_code
        == "ai_catalog_version_unsupported"
    )


def test_score_is_not_trust_evidence() -> None:
    """Relevance score is never trust/safety evidence."""
    resp = decode_search_response(SEARCH_RESPONSE)
    # Score is carried as a plain integer — no trust/safety semantics.
    assert resp.results[0].score == 95
    assert isinstance(resp.results[0].score, int)

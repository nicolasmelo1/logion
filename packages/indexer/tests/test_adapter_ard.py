# SPDX-License-Identifier: MIT
"""Tests for the ARD adapter."""

from __future__ import annotations

import json

from logion_indexer.adapters.ard import ARDAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

REGISTRY = "https://registry.example.com"
SEARCH_URL = f"{REGISTRY}/search"

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


def _transport() -> FakeTransport:
    transport = FakeTransport()
    transport.set_post_response(
        SEARCH_URL,
        HttpResponse(
            200,
            json.dumps(SEARCH_RESPONSE).encode("utf-8"),
        ),
    )
    return transport


def test_search_yields_resources() -> None:
    transport = _transport()
    adapter = ARDAdapter(transport)
    result = adapter.search(REGISTRY, query_text="weather agent")
    assert len(result.resources) == 2


def test_referrals_collected() -> None:
    transport = _transport()
    adapter = ARDAdapter(transport)
    result = adapter.search(REGISTRY, query_text="test")
    assert "https://finder.nlweb.ai/search" in result.referrals


def test_relevance_score_in_metadata() -> None:
    transport = _transport()
    adapter = ARDAdapter(transport)
    result = adapter.search(REGISTRY, query_text="test")
    assistant = next(
        r for r in result.resources if "assistant" in r.canonical_uri
    )
    metadata = dict(assistant.channels[0].metadata)
    assert metadata["relevance_score"] == "95"


def test_relevance_score_not_in_evidence() -> None:
    """Relevance score is never trust/safety evidence."""
    transport = _transport()
    adapter = ARDAdapter(transport)
    result = adapter.search(REGISTRY, query_text="test")
    for r in result.resources:
        # Score is in channel metadata only, not in any evidence field.
        assert r.bundle is None


def test_page_token_preserved() -> None:
    transport = _transport()
    adapter = ARDAdapter(transport)
    result = adapter.search(REGISTRY, query_text="test")
    assert result.page_token == "next="


def test_resource_type_mapping() -> None:
    transport = _transport()
    adapter = ARDAdapter(transport)
    result = adapter.search(REGISTRY, query_text="test")
    by_uri = {r.canonical_uri: r for r in result.resources}
    assert (
        by_uri["air:urn:air:acme.com:agent:assistant"].resource_type
        == "mcp_server"
    )
    assert (
        by_uri["air:urn:air:example.com:mcp:weather"].resource_type
        == "mcp_server"
    )


def test_search_error_returns_errors() -> None:
    transport = FakeTransport()
    transport.set_post_response(
        SEARCH_URL,
        HttpResponse(400, b'{"code":"INVALID_ARGUMENT"}'),
    )
    adapter = ARDAdapter(transport)
    result = adapter.search(REGISTRY, query_text="test")
    assert len(result.errors) > 0
    assert len(result.resources) == 0


def test_discover_iterable() -> None:
    transport = _transport()
    adapter = ARDAdapter(transport)
    resources = list(adapter.discover(REGISTRY, query_text="test"))
    assert len(resources) == 2

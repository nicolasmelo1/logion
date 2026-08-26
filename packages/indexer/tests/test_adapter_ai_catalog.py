# SPDX-License-Identifier: MIT
"""Tests for the AI Catalog adapter."""

from __future__ import annotations

import json

from logion_indexer.adapters.ai_catalog import AICatalogAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

CATALOG_URL = "https://example.com/.well-known/ai-catalog.json"

CATALOG = {
    "specVersion": "1.0",
    "host": {"displayName": "Test Host"},
    "entries": [
        {
            "identifier": "urn:air:example.com:mcp:weather",
            "displayName": "Weather Service",
            "type": "application/mcp-server-card+json",
            "url": "https://api.example.com/mcp/weather",
            "description": "Weather MCP server.",
            "tags": ["weather", "tools"],
            "capabilities": ["WeatherTool"],
        },
        {
            "identifier": "urn:air:example.com:agent:research",
            "displayName": "Research Agent",
            "type": "application/a2a-agent-card+json",
            "url": "https://agents.example.com/research",
        },
        {
            "identifier": "urn:air:example.com:catalog:nested",
            "type": "application/ai-catalog+json",
            "url": "https://example.com/catalogs/nested.json",
        },
        {
            "identifier": "urn:air:example.com:registry:main",
            "type": "application/ai-registry+json",
            "url": "https://registry.example.com/api/v1/",
        },
        {
            "identifier": "urn:air:example.com:custom:unknown",
            "type": "application/x-unknown-type",
            "url": "https://example.com/unknown",
        },
    ],
}


def _transport() -> FakeTransport:
    transport = FakeTransport()
    transport.set_response(
        CATALOG_URL,
        HttpResponse(
            200,
            json.dumps(CATALOG).encode("utf-8"),
        ),
    )
    return transport


def test_discover_yields_resources() -> None:
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    resources = list(adapter.discover(CATALOG_URL))
    # 4 resources: weather, research, registry, unknown.
    # Nested catalog is not yielded as a resource.
    assert len(resources) == 4


def test_nested_catalog_collected() -> None:
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    result = adapter.crawl(CATALOG_URL)
    assert "https://example.com/catalogs/nested.json" in result.nested_catalogs


def test_registry_url_collected() -> None:
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    result = adapter.crawl(CATALOG_URL)
    assert "https://registry.example.com/api/v1/" in result.registry_urls


def test_resource_type_mapping() -> None:
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    resources = list(adapter.discover(CATALOG_URL))
    by_uri = {r.canonical_uri: r for r in resources}
    assert (
        by_uri["air:urn:air:example.com:mcp:weather"].resource_type
        == "mcp_server"
    )
    assert (
        by_uri["air:urn:air:example.com:agent:research"].resource_type
        == "mcp_server"
    )
    assert (
        by_uri["air:urn:air:example.com:registry:main"].resource_type
        == "registry"
    )
    assert (
        by_uri["air:urn:air:example.com:custom:unknown"].resource_type
        == "artifact"
    )


def test_canonical_uri_uses_air_prefix() -> None:
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    resources = list(adapter.discover(CATALOG_URL))
    assert resources[0].canonical_uri.startswith("air:urn:air:")


def test_channel_has_ai_catalog_slug() -> None:
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    resources = list(adapter.discover(CATALOG_URL))
    assert resources[0].channels[0].hub_slug == "ai-catalog"
    assert resources[0].channels[0].hub_url == CATALOG_URL


def test_unknown_type_preserved() -> None:
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    resources = list(adapter.discover(CATALOG_URL))
    unknown = [r for r in resources if r.resource_type == "artifact"]
    assert len(unknown) == 1


def test_no_digest_created() -> None:
    """A selection-descriptor digest must NOT create a ResourceVersion."""
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    resources = list(adapter.discover(CATALOG_URL))
    # bundle is None — no digest computed.
    for r in resources:
        assert r.bundle is None


def test_fetch_failure_returns_errors() -> None:
    transport = FakeTransport()
    transport.set_response(CATALOG_URL, HttpResponse(404, b"not found"))
    adapter = AICatalogAdapter(transport)
    result = adapter.crawl(CATALOG_URL)
    assert len(result.errors) > 0
    assert len(result.resources) == 0


def test_limit_caps_results() -> None:
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    resources = list(adapter.discover(CATALOG_URL, limit=2))
    assert len(resources) == 2


def test_capabilities_preserved() -> None:
    transport = _transport()
    adapter = AICatalogAdapter(transport)
    resources = list(adapter.discover(CATALOG_URL))
    weather = next(r for r in resources if "weather" in r.canonical_uri)
    assert weather.declared_capabilities is not None
    assert weather.declared_capabilities["capabilities"] == ["WeatherTool"]

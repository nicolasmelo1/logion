# SPDX-License-Identifier: MIT
"""Tests for the AI Catalog v1.0 codec and models."""

from __future__ import annotations

import pytest

from logion_indexer.ai_catalog.v1_0 import (
    CatalogEntry,
)
from logion_indexer.ai_catalog.v1_0.codec import (
    AICatalogDecodeError,
    AICatalogVersionUnsupported,
    decode_catalog,
    encode_catalog,
)

#: Minimal valid catalog.
MINIMAL = {
    "specVersion": "1.0",
    "entries": [
        {
            "identifier": "urn:air:example.com:mcp:weather",
            "type": "application/mcp-server-card+json",
            "url": "https://api.example.com/mcp/weather",
        }
    ],
}

#: Full catalog with host, publisher, trust manifest, and extra fields.
FULL = {
    "specVersion": "1.0",
    "host": {
        "displayName": "Acme Services",
        "identifier": "did:web:acme.com",
        "documentationUrl": "https://docs.acme.com",
    },
    "entries": [
        {
            "identifier": "urn:air:acme.com:agent:finance",
            "displayName": "Finance Agent",
            "type": "application/a2a-agent-card+json",
            "url": "https://api.acme.com/agents/finance.json",
            "description": "Finance trading agent.",
            "tags": ["finance", "trading"],
            "version": "2.1.0",
            "updatedAt": "2026-03-15T10:00:00Z",
            "publisher": {
                "identifier": "did:web:acme.com",
                "displayName": "Acme",
                "identityType": "did",
            },
            "trustManifest": {
                "identity": "did:web:acme.com:agent:finance",
                "identityType": "did",
                "attestations": [
                    {
                        "type": "SOC2-Type2",
                        "uri": "https://trust.acme.com/soc2.pdf",
                        "digest": "sha256:abcd1234",
                    }
                ],
                "provenance": [
                    {
                        "relation": "publishedFrom",
                        "sourceId": "https://github.com/acme/finance",
                    }
                ],
                "signature": "eyJhbG...",
            },
            "x-custom-field": "custom-value",
        },
        {
            "identifier": "urn:air:acme.com:catalog:nested",
            "type": "application/ai-catalog+json",
            "url": "https://acme.com/catalogs/nested.json",
        },
    ],
    "x-top-level": "top-value",
}


def test_decode_minimal() -> None:
    catalog = decode_catalog(MINIMAL)
    assert catalog.spec_version == "1.0"
    assert len(catalog.entries) == 1
    entry = catalog.entries[0]
    assert entry.identifier == "urn:air:example.com:mcp:weather"
    assert entry.type == "application/mcp-server-card+json"
    assert entry.url == "https://api.example.com/mcp/weather"
    assert entry.data is None
    assert entry.display_name is None
    assert entry.is_nested_catalog is False


def test_decode_full() -> None:
    """Smoke test: the FULL catalog decodes without error."""
    catalog = decode_catalog(FULL)
    assert catalog.spec_version == "1.0"
    assert len(catalog.entries) == 2


def test_decode_full_host() -> None:
    """Host block is decoded into the catalog's host field."""
    catalog = decode_catalog(FULL)
    assert catalog.host is not None
    assert catalog.host.display_name == "Acme Services"
    assert catalog.host.identifier == "did:web:acme.com"


def test_decode_full_entry_fields() -> None:
    """First entry's scalar fields are decoded."""
    catalog = decode_catalog(FULL)
    entry = catalog.entries[0]
    assert entry.display_name == "Finance Agent"
    assert entry.version == "2.1.0"
    assert entry.tags == ("finance", "trading")


def test_decode_full_publisher() -> None:
    """Publisher block is decoded into the entry's publisher field."""
    catalog = decode_catalog(FULL)
    entry = catalog.entries[0]
    assert entry.publisher is not None
    assert entry.publisher.display_name == "Acme"
    assert entry.publisher.identity_type == "did"


def test_decode_full_trust_manifest() -> None:
    """Trust manifest, attestations, and provenance are decoded."""
    catalog = decode_catalog(FULL)
    entry = catalog.entries[0]
    tm = entry.trust_manifest
    assert tm is not None
    assert tm.identity == "did:web:acme.com:agent:finance"
    assert tm.signature == "eyJhbG..."
    assert len(tm.attestations) == 1
    assert tm.attestations[0].type == "SOC2-Type2"
    assert tm.attestations[0].digest == "sha256:abcd1234"
    assert len(tm.provenance) == 1
    assert tm.provenance[0].relation == "publishedFrom"


def test_decode_full_entry_extra_fields() -> None:
    """Unknown per-entry fields are preserved in ``entry.extra``."""
    catalog = decode_catalog(FULL)
    entry = catalog.entries[0]
    extra_keys = [k for k, _ in entry.extra]
    assert "x-custom-field" in extra_keys


def test_decode_full_nested_catalog() -> None:
    """A nested-catalog entry is flagged as such."""
    catalog = decode_catalog(FULL)
    nested = catalog.entries[1]
    assert nested.is_nested_catalog is True


def test_decode_full_top_level_extra() -> None:
    """Unknown top-level fields are preserved in ``catalog.extra``."""
    catalog = decode_catalog(FULL)
    top_extra = [k for k, _ in catalog.extra]
    assert "x-top-level" in top_extra


def test_roundtrip_encode_decode() -> None:
    catalog = decode_catalog(FULL)
    encoded = encode_catalog(catalog)
    # Re-decode and verify core fields survived.
    catalog2 = decode_catalog(encoded)
    assert catalog2.spec_version == catalog.spec_version
    assert len(catalog2.entries) == len(catalog.entries)
    assert catalog2.entries[0].identifier == catalog.entries[0].identifier
    assert catalog2.entries[0].trust_manifest is not None
    assert (
        catalog2.entries[0].trust_manifest.signature
        == catalog.entries[0].trust_manifest.signature
    )


def test_version_unsupported() -> None:
    doc = {"specVersion": "2.0", "entries": []}
    with pytest.raises(AICatalogVersionUnsupported) as exc_info:
        decode_catalog(doc)
    assert "ai_catalog_version_unsupported" in str(exc_info.value.error_code)


def test_missing_spec_version() -> None:
    doc = {"entries": []}
    with pytest.raises(AICatalogDecodeError):
        decode_catalog(doc)


def test_missing_entries() -> None:
    doc = {"specVersion": "1.0"}
    with pytest.raises(AICatalogDecodeError):
        decode_catalog(doc)


def test_url_data_mutually_exclusive() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "url": "https://example.com",
                "data": {"foo": "bar"},
            }
        ],
    }
    with pytest.raises(AICatalogDecodeError, match="mutually exclusive"):
        decode_catalog(doc)


def test_url_or_data_required() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
            }
        ],
    }
    with pytest.raises(AICatalogDecodeError, match=r"url.*data"):
        decode_catalog(doc)


def test_empty_entries() -> None:
    doc = {"specVersion": "1.0", "entries": []}
    catalog = decode_catalog(doc)
    assert len(catalog.entries) == 0


def test_display_or_fallback() -> None:
    entry = CatalogEntry(
        identifier="urn:air:example.com:mcp:weather",
        type="application/mcp-server-card+json",
        url="https://example.com",
    )
    assert entry.display_or_fallback == "weather"

    entry_named = CatalogEntry(
        identifier="urn:air:example.com:mcp:weather",
        type="application/mcp-server-card+json",
        url="https://example.com",
        display_name="Weather Service",
    )
    assert entry_named.display_or_fallback == "Weather Service"


def test_conformance_level_trusted() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "url": "https://example.com",
                "trustManifest": {
                    "identity": "did:web:test.com:item",
                    "signature": "sig",
                },
            }
        ],
    }
    catalog = decode_catalog(doc)
    assert catalog.conformance_level == "trusted"


def test_conformance_level_minimal() -> None:
    catalog = decode_catalog(MINIMAL)
    assert catalog.conformance_level == "minimal"


def test_inline_data() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "data": {"name": "inline"},
            }
        ],
    }
    catalog = decode_catalog(doc)
    assert catalog.entries[0].data == {"name": "inline"}
    assert catalog.entries[0].url is None


def test_unknown_type_preserved() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/x-custom-type",
                "url": "https://example.com",
            }
        ],
    }
    catalog = decode_catalog(doc)
    assert catalog.entries[0].type == "application/x-custom-type"

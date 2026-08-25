# SPDX-License-Identifier: MIT
"""Tests for the AI Catalog v1.0 conformance validation."""

from __future__ import annotations

from logion_indexer.ai_catalog.v1_0.conformance import (
    validate_catalog,
    validate_document,
)

VALID = {
    "specVersion": "1.0",
    "entries": [
        {
            "identifier": "urn:air:example.com:mcp:weather",
            "type": "application/mcp-server-card+json",
            "url": "https://api.example.com/mcp/weather",
        }
    ],
}


def test_valid_document_passes() -> None:
    result = validate_document(VALID)
    assert result.passed
    assert result.level == "minimal"


def test_trusted_conformance() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "url": "https://example.com",
                "trustManifest": {
                    "identity": "did:web:test.com",
                    "signature": "sig",
                },
            }
        ],
    }
    result = validate_document(doc)
    assert result.passed
    assert result.level == "trusted"


def test_unsupported_version_fails() -> None:
    doc = {"specVersion": "2.0", "entries": []}
    result = validate_document(doc)
    assert not result.passed
    assert any("unsupported" in e for e in result.errors)


def test_duplicate_identifier_fails() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "url": "https://example.com/a",
            },
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "url": "https://example.com/b",
            },
        ],
    }
    result = validate_document(doc)
    assert not result.passed
    assert any("duplicate" in e for e in result.errors)


def test_duplicate_identifier_with_version_allowed() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "url": "https://example.com/a",
                "version": "1.0.0",
            },
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "url": "https://example.com/b",
                "version": "2.0.0",
            },
        ],
    }
    result = validate_document(doc)
    assert result.passed


def test_unknown_type_warning() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/x-custom",
                "url": "https://example.com",
            }
        ],
    }
    result = validate_document(doc)
    assert result.passed
    assert any("unknown type" in w for w in result.warnings)


def test_unknown_type_strict_fails() -> None:
    doc = {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/x-custom",
                "url": "https://example.com",
            }
        ],
    }
    result = validate_document(doc, allow_unknown_types=False)
    assert not result.passed


def test_validate_catalog_directly() -> None:
    from logion_indexer.ai_catalog.v1_0.codec import decode_catalog

    catalog = decode_catalog(VALID)
    result = validate_catalog(catalog)
    assert result.passed

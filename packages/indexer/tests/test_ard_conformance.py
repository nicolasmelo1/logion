# SPDX-License-Identifier: MIT
"""Tests for the ARD v0.9 conformance validation."""

from __future__ import annotations

from logion_indexer.ard.v0_9.conformance import (
    validate_error_response,
    validate_search_response,
)

VALID_RESPONSE = {
    "results": [
        {
            "identifier": "urn:air:acme.com:agent:assistant",
            "displayName": "Corporate Assistant",
            "type": "application/a2a-agent-card+json",
            "url": "https://api.acme.com/agents/assistant.json",
            "score": 95,
        }
    ],
    "referrals": [],
}


def test_valid_response_passes() -> None:
    result = validate_search_response(VALID_RESPONSE)
    assert result.passed


def test_score_out_of_range_fails() -> None:
    doc = {
        "results": [
            {
                "identifier": "urn:air:test:test:item",
                "type": "application/test+json",
                "url": "https://example.com",
                "score": 150,
            }
        ],
    }
    result = validate_search_response(doc)
    assert not result.passed
    assert any("outside 0-100" in e for e in result.errors)


def test_score_warning_not_trust() -> None:
    result = validate_search_response(VALID_RESPONSE)
    assert result.passed
    assert any("not trust/safety evidence" in w for w in result.warnings)


def test_empty_identifier_fails() -> None:
    doc = {
        "results": [
            {
                "identifier": "",
                "type": "application/test+json",
                "url": "https://example.com",
            }
        ],
    }
    result = validate_search_response(doc)
    assert not result.passed


def test_referral_without_url_fails() -> None:
    doc = {
        "results": [],
        "referrals": [
            {
                "identifier": "urn:air:test:registry:demo",
                "displayName": "Demo",
            }
        ],
    }
    result = validate_search_response(doc)
    assert not result.passed
    assert any("url" in e for e in result.errors)


def test_valid_error_response() -> None:
    doc = {"code": "INVALID_ARGUMENT", "message": "bad query"}
    result = validate_error_response(doc)
    assert result.passed


def test_unknown_error_code_fails() -> None:
    doc = {"code": "UNKNOWN_CODE", "message": "something"}
    result = validate_error_response(doc)
    assert not result.passed


def test_ard_and_ai_catalog_errors_separate() -> None:
    """AI Catalog and ARD have separate error codes."""
    from logion_indexer.ai_catalog.v1_0.codec import (
        AICatalogVersionUnsupported,
    )
    from logion_indexer.ard.v0_9.codec import ARDVersionUnsupported

    assert (
        AICatalogVersionUnsupported.error_code
        == "ai_catalog_version_unsupported"
    )
    assert ARDVersionUnsupported.error_code == "ard_version_unsupported"
    assert (
        AICatalogVersionUnsupported.error_code
        != ARDVersionUnsupported.error_code
    )

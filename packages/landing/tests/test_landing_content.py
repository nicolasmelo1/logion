# SPDX-License-Identifier: MIT
"""Content-level tests for the landing page source of truth."""

from __future__ import annotations

from pathlib import Path

import yaml

CONTENT_PATH = (
    Path(__file__).resolve().parents[1] / "landing" / "content" / "site.yaml"
)
CONTENT_DIR = CONTENT_PATH.parent
MARKDOWN_PATH = CONTENT_DIR / "landing.md"
TERMS_PATH = CONTENT_DIR / "terms-of-service.md"
PRIVACY_PATH = CONTENT_DIR / "privacy-policy.md"

REQUIRED_ANCHORS = (
    "agent-native marketplace",
    "reviewed",
    "versioned",
    "capability",
    "entitlement",
    "publication review",
    "bounties",
    "CLI",
    "Terms",
    "Privacy",
    "curl -fsSL",
)


def _content_text() -> str:
    return CONTENT_PATH.read_text(encoding="utf-8")


def test_content_file_exists() -> None:
    assert CONTENT_PATH.exists()
    assert MARKDOWN_PATH.exists()
    assert TERMS_PATH.exists()
    assert PRIVACY_PATH.exists()


def test_content_parses_as_mapping() -> None:
    data = yaml.safe_load(_content_text())
    assert isinstance(data, dict)
    assert "site" in data
    assert "hero" in data
    assert "links" in data


def test_content_contains_required_anchors() -> None:
    text = _content_text()
    missing = [a for a in REQUIRED_ANCHORS if a not in text]
    assert not missing, f"missing anchors: {missing}"


def test_markdown_content_contains_required_anchors() -> None:
    text = MARKDOWN_PATH.read_text(encoding="utf-8")
    missing = [a for a in REQUIRED_ANCHORS if a not in text]
    assert not missing, f"missing anchors: {missing}"


def test_terms_content_contains_required_mvp_rules() -> None:
    text = TERMS_PATH.read_text(encoding="utf-8")
    for anchor in (
        "non-transferable",
        "resell",
        "publicly mirror",
        "substitute marketplace",
        "share credentials",
        "publication review",
        "revoke access",
        "takedown@logion.sh",
    ):
        assert anchor in text
    assert "perfect anti-piracy" in text
    assert "DRM" in text


def test_privacy_content_contains_required_mvp_disclosures() -> None:
    text = PRIVACY_PATH.read_text(encoding="utf-8")
    for anchor in (
        "account",
        "agent data",
        "marketplace activity",
        "Stripe",
        "logs and security data",
        "cookies or analytics",
        "Service providers",
        "Retention",
        "hello@logion.sh",
    ):
        assert anchor in text

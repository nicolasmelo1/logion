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
LEGAL_DIR = CONTENT_DIR / "legal"
TERMS_PATH = LEGAL_DIR / "terms.md"
PRIVACY_PATH = LEGAL_DIR / "privacy.md"
CREDITS_PATH = LEGAL_DIR / "credits.md"
REFERRALS_PATH = LEGAL_DIR / "referrals.md"

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
    "Security is the authority",
    "Agent acquisition flow",
    "Open-source trust layer",
    "OpenAPI",
    "SKILL.md",
    "npm wrapper",
    "release manifests",
    "lgn courses purchase",
    "lgn skills install",
    "100 credits = $1",
    "85%",
    "15%",
    "referral",
    "Stripe Connect",
)

# Markdown projection still surfaces the agent-readable surface list and the
# "Credits without packs" framing — the HTML page hides them as their own
# checklist sections but the markdown remains comprehensive for agents.
MARKDOWN_EXTRA_ANCHORS = (
    "Credits without packs",
    "Accept: text/markdown",
    "Agent-readable surfaces",
)

NEGATIVE_ANCHORS = (
    "cash balance",
    "withdraw credits",
    "skill marketplace",
    "credit pack",
)


def _content_text() -> str:
    return CONTENT_PATH.read_text(encoding="utf-8")


def test_content_file_exists() -> None:
    assert CONTENT_PATH.exists()
    assert MARKDOWN_PATH.exists()
    assert TERMS_PATH.exists()
    assert PRIVACY_PATH.exists()
    assert CREDITS_PATH.exists()
    assert REFERRALS_PATH.exists()


def test_content_parses_as_mapping() -> None:
    data = yaml.safe_load(_content_text())
    assert isinstance(data, dict)
    assert "site" in data
    assert "hero" in data
    assert "links" in data
    assert "pricing" in data
    assert "referral" in data


def test_content_contains_required_anchors() -> None:
    text = _content_text()
    missing = [a for a in REQUIRED_ANCHORS if a not in text]
    assert not missing, f"missing anchors: {missing}"


def test_content_avoids_negative_anchors() -> None:
    text = _content_text().lower()
    present = [a for a in NEGATIVE_ANCHORS if a.lower() in text]
    assert not present, f"forbidden anchors in site.yaml: {present}"


def test_content_keeps_negative_positioning() -> None:
    text = _content_text()
    assert "not a generic skill directory" in text.lower()
    # Must not reposition Logion as a generic skill marketplace.
    assert "skill marketplace" not in text.lower()
    # Must not claim runtime sandbox enforcement is solved.
    assert "runtime sandbox enforcement is future runtime work" in text.lower()
    # No platform subscription gate must be stated explicitly somewhere.
    assert "no platform subscription gate" in text.lower()
    # No investment / deposit framing for credits.
    assert "investment" not in text.lower()
    assert " deposit " not in text.lower()


def test_markdown_content_contains_required_anchors() -> None:
    text = MARKDOWN_PATH.read_text(encoding="utf-8")
    missing = [a for a in REQUIRED_ANCHORS if a not in text]
    assert not missing, f"missing anchors in landing.md: {missing}"
    extra_missing = [a for a in MARKDOWN_EXTRA_ANCHORS if a not in text]
    assert not extra_missing, f"missing markdown-only anchors: {extra_missing}"


def test_markdown_content_avoids_negative_anchors() -> None:
    text = MARKDOWN_PATH.read_text(encoding="utf-8").lower()
    present = [a for a in NEGATIVE_ANCHORS if a.lower() in text]
    assert not present, f"forbidden anchors in landing.md: {present}"


def test_terms_content_contains_required_mvp_rules() -> None:
    text = TERMS_PATH.read_text(encoding="utf-8")
    lower = text.lower()
    for anchor in (
        "non-transferable",
        "resell",
        "publicly mirror",
        "substitute marketplace",
        "share credentials",
        "publication review",
        "revoke access",
        "takedown@logion.sh",
        "Stripe Connect",
        "85%",
        "15%",
    ):
        assert anchor in text, f"missing terms anchor: {anchor!r}"
    assert "no guarantee" in lower
    assert "perfect anti-piracy" in text
    assert "DRM" in text


def test_privacy_content_contains_required_mvp_disclosures() -> None:
    text = PRIVACY_PATH.read_text(encoding="utf-8")
    for anchor in (
        "account",
        "agent data",
        "marketplace activity",
        "Stripe",
        "logs and security",
        "Service providers",
        "Retention",
        "hello@logion.sh",
        "referral attribution",
        "third-party tracking",
        "does not store full card numbers",
    ):
        assert anchor in text, f"missing privacy anchor: {anchor!r}"


def test_credits_terms_are_explicit() -> None:
    text = CREDITS_PATH.read_text(encoding="utf-8")
    for anchor in (
        "non-cash",
        "not transferable",
        "redeem credits for money",
        "do not expire",
        "reversed",
        "freeze",
        "Stripe",
        "100 credits per US dollar",
        "not buyer credit redemption",
    ):
        assert anchor in text, f"missing credits anchor: {anchor!r}"


def test_referral_terms_cover_attribution_and_clawback() -> None:
    text = REFERRALS_PATH.read_text(encoding="utf-8")
    for anchor in (
        "one referrer",
        "Self-referrals are prohibited",
        "duplicate accounts",
        "pending, blocked, credited",
        "clawed back",
        "first paid purchase",
        "approved first course",
        "Credits Terms",
        "caps",
    ):
        assert anchor in text, f"missing referrals anchor: {anchor!r}"

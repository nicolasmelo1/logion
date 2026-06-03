# SPDX-License-Identifier: MIT
"""Content-level tests for the landing page source of truth."""

from __future__ import annotations

from pathlib import Path

import yaml

CONTENT_PATH = (
    Path(__file__).resolve().parents[1] / "landing" / "content" / "site.yaml"
)

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
)


def _content_text() -> str:
    return CONTENT_PATH.read_text(encoding="utf-8")


def test_content_file_exists() -> None:
    assert CONTENT_PATH.exists()


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

# SPDX-License-Identifier: MIT
"""Deterministic taxonomy suggestions from local course bundle text.

Reads SKILL.md frontmatter and body plus an optional
``course/capabilities.yaml`` summary, then maps keywords to category
slugs and tag slugs. No LLM calls — the mapping is deterministic so
agents get reproducible suggestions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from cli._taxonomy import (
    RESERVED_TAG_SLUGS,
    TaxonomyValidationError,
    normalize_tag,
)
from cli.commands.courses._taxonomy_data import (
    CATEGORY_KEYWORDS,
    STOP_WORDS,
)

_SKILL_BODY_READ_BYTES = 4096
_MIN_TOKEN_LENGTH = 3


def _read_skill_frontmatter(skill_path: Path) -> dict[str, Any] | None:
    """Parse YAML frontmatter from SKILL.md, returning None if absent."""
    if not skill_path.is_file():
        return None
    try:
        text = skill_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---\n", 3)
    if end < 0:
        stripped = text.rstrip()
        if stripped.endswith("---") and text.count("---") >= 2:
            end = stripped.rfind("---")
            block = text[3:end].rstrip()
        else:
            return None
    else:
        block = text[3:end]
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_skill_body_head(skill_path: Path) -> str:
    """Return the first 4 KB of SKILL.md body (after frontmatter)."""
    if not skill_path.is_file():
        return ""
    try:
        text = skill_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if text.startswith("---"):
        end = text.find("\n---\n", 3)
        body = text[end + 5 :] if end >= 0 else ""
    else:
        body = text
    return body[:_SKILL_BODY_READ_BYTES]


def _read_capabilities_summary(bundle_dir: Path) -> str:
    """Return a text blob from ``course/capabilities.yaml`` if present."""
    cap_path = bundle_dir / "course" / "capabilities.yaml"
    if not cap_path.is_file():
        return ""
    try:
        data = yaml.safe_load(cap_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return ""
    if not isinstance(data, dict):
        return ""
    parts: list[str] = []
    summary = data.get("summary")
    if isinstance(summary, str):
        parts.append(summary)
    tools = data.get("tools")
    if isinstance(tools, list):
        parts.extend(str(t) for t in tools)
    return " ".join(parts)


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, drop stops and short tokens."""
    raw = re.findall(r"[a-zA-Z0-9_-]+", text.lower())
    tokens: list[str] = []
    for word in raw:
        for segment in word.split("-"):
            segment = segment.strip("-")
            if len(segment) >= _MIN_TOKEN_LENGTH and segment not in STOP_WORDS:
                tokens.append(segment)
        if len(word) >= _MIN_TOKEN_LENGTH and word not in STOP_WORDS:
            tokens.append(word)
    return tokens


def _suggest_categories(tokens: list[str]) -> list[str]:
    """Map tokens to category slugs by keyword overlap."""
    token_set = set(tokens)
    matches: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if token_set & keywords:
            matches.append(category)
    if not matches:
        return ["other"]
    # CATEGORY_SLUGS is a frozenset (unordered); iterate CATEGORY_KEYWORDS
    # keys instead so the output order is deterministic across processes.
    match_set = set(matches)
    return [c for c in CATEGORY_KEYWORDS if c in match_set]


def _suggest_tags(tokens: list[str]) -> tuple[list[str], list[str]]:
    """Convert tokens to valid tag slugs, rejecting reserved labels.

    Returns ``(tags, rejected_reserved)``.
    """
    seen: set[str] = set()
    tags: list[str] = []
    rejected: list[str] = []
    for token in tokens:
        # Check reserved labels before normalize_tag, which raises on
        # reserved slugs — we want to report them, not silently drop.
        normalized = token.strip().lower().replace(" ", "-").replace("_", "-")
        if normalized in RESERVED_TAG_SLUGS:
            if normalized not in seen:
                seen.add(normalized)
                rejected.append(normalized)
            continue
        try:
            tag = normalize_tag(token)
        except TaxonomyValidationError:
            continue
        if tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags[:20], rejected


def suggest_taxonomy(
    bundle_dir: Path,
) -> dict[str, Any]:
    """Produce deterministic category and tag suggestions for a bundle.

    Reads ``SKILL.md`` frontmatter (name, description) and body, plus
    ``course/capabilities.yaml`` summary/tools. No network or LLM calls.
    """
    sources: list[str] = []
    skill_path = bundle_dir / "SKILL.md"
    text_parts: list[str] = []

    frontmatter = _read_skill_frontmatter(skill_path)
    if frontmatter is not None:
        sources.append("SKILL.md")
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if isinstance(name, str):
            text_parts.append(name)
        if isinstance(description, str):
            text_parts.append(description)

    body_head = _read_skill_body_head(skill_path)
    if body_head:
        if "SKILL.md" not in sources:
            sources.append("SKILL.md")
        text_parts.append(body_head)

    cap_summary = _read_capabilities_summary(bundle_dir)
    if cap_summary:
        sources.append("course/capabilities.yaml")
        text_parts.append(cap_summary)

    combined = " ".join(text_parts)
    tokens = _tokenize(combined)

    category_suggestions = _suggest_categories(tokens)
    tag_suggestions, rejected_reserved = _suggest_tags(tokens)

    return {
        "category_suggestions": category_suggestions,
        "tag_suggestions": tag_suggestions,
        "rejected_reserved": rejected_reserved,
        "source": sources,
    }

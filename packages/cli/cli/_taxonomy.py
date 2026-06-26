# SPDX-License-Identifier: MIT
"""CLI-side taxonomy helpers mirroring the backend normalization rules.

These are duplicated rather than imported from the backend so the CLI
can validate locally without a network round-trip. The rules must stay
in sync with the backend taxonomy module.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

CATEGORY_SLUGS: frozenset[str] = frozenset({
    "automation",
    "code-review",
    "data",
    "devops",
    "documentation",
    "finance",
    "marketing",
    "media",
    "productivity",
    "research",
    "security",
    "testing",
    "writing",
    "other",
})
DEFAULT_CATEGORY = "other"

RESERVED_TAG_SLUGS: frozenset[str] = frozenset({
    "official",
    "verified",
    "trusted",
    "featured",
    "logion",
    "admin",
    "staff",
    "platform",
    "security-audited",
})

TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class TaxonomyValidationError(ValueError):
    """Raised when a category or tag fails normalization."""


def normalize_category(value: str | None) -> str:
    """Return a validated category slug, defaulting to ``other``."""
    if value is None:
        return DEFAULT_CATEGORY
    slug = value.strip().lower()
    if not slug:
        return DEFAULT_CATEGORY
    if slug not in CATEGORY_SLUGS:
        raise TaxonomyValidationError(f"Unknown category: {value}")
    return slug


def normalize_tag(value: str) -> str:
    """Normalize a single tag slug and reject reserved/invalid labels."""
    if value is None:
        raise TaxonomyValidationError("Invalid tag after normalization: None")
    tag = value.strip().lower()
    tag = tag.replace(" ", "-").replace("_", "-")
    # Collapse repeated hyphens that the above may have introduced.
    tag = re.sub(r"-+", "-", tag)
    tag = tag.strip("-")
    if not tag:
        raise TaxonomyValidationError("Invalid tag after normalization: empty")
    if tag in RESERVED_TAG_SLUGS:
        raise TaxonomyValidationError(f"Reserved tag is not allowed: {tag}")
    if not TAG_RE.match(tag):
        raise TaxonomyValidationError(
            f"Invalid tag after normalization: {tag}"
        )
    return tag


def normalize_tags(
    values: Sequence[str],
    *,
    max_count: int = 20,
) -> list[str]:
    """Normalize a sequence of tags, preserving first-seen order.

    Duplicates (after normalization) collapse. Raises if the normalized
    set exceeds *max_count* or if any tag is reserved/invalid.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        tag = normalize_tag(raw)
        if tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    if len(result) > max_count:
        raise TaxonomyValidationError(
            f"Too many tags: {len(result)} (max {max_count})"
        )
    return result


def tag_search_tokens(tag: str) -> set[str]:
    """Return the full normalized tag plus each hyphen segment.

    ``pr-review`` yields ``{"pr-review", "pr", "review"}``. The backend
    uses these segments for relevance-search eligibility (not for tag
    filters, which are prefix-only); the CLI mirrors it for local
    suggestion expansion.
    """
    normalized = normalize_tag(tag)
    segments = normalized.split("-")
    tokens: set[str] = {normalized}
    tokens.update(seg for seg in segments if seg)
    return tokens

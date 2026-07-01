# SPDX-License-Identifier: MIT
"""Canonical first-party course identity constants.

These constants pin the stable, canonical identifiers for the
first-party companion course so that every code path — onboarding,
installer, CLI commands — refers to the same UUID-identified course
instead of the human-friendly slug.
"""

from __future__ import annotations

from dataclasses import dataclass

LOGION_MARKETPLACE_COMPANION_SLUG = "logion-marketplace-companion"
LOGION_MARKETPLACE_COMPANION_COURSE_ID = "5ddf32c6-e139-4056-ac94-c4a231bfd932"
LOGION_MARKETPLACE_COMPANION_NAME = "Logion Marketplace Companion"


@dataclass(frozen=True)
class FirstPartyCourse:
    """A canonical first-party course entry."""

    slug: str
    course_id: str
    title: str


_REGISTRY: dict[str, FirstPartyCourse] = {
    LOGION_MARKETPLACE_COMPANION_SLUG: FirstPartyCourse(
        slug=LOGION_MARKETPLACE_COMPANION_SLUG,
        course_id=LOGION_MARKETPLACE_COMPANION_COURSE_ID,
        title=LOGION_MARKETPLACE_COMPANION_NAME,
    ),
}

_COURSE_IDS: frozenset[str] = frozenset(
    c.course_id for c in _REGISTRY.values()
)


def get_first_party_course(slug: str) -> FirstPartyCourse | None:
    """Return the first-party course for *slug*, or ``None``."""
    return _REGISTRY.get(slug)


def require_first_party_course(slug: str) -> FirstPartyCourse:
    """Return the first-party course for *slug* or raise ``ValueError``."""
    course = _REGISTRY.get(slug)
    if course is None:
        raise ValueError(f"unknown first-party course slug: {slug!r}")
    return course


def is_first_party_course_id(course_id: str) -> bool:
    """Return ``True`` when *course_id* is a known first-party UUID."""
    return course_id in _COURSE_IDS

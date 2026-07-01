# SPDX-License-Identifier: MIT
"""Tests for ``cli._first_party`` canonical identity constants."""

from __future__ import annotations

import pytest

from cli._first_party import (
    LOGION_MARKETPLACE_COMPANION_COURSE_ID,
    LOGION_MARKETPLACE_COMPANION_NAME,
    LOGION_MARKETPLACE_COMPANION_SLUG,
    FirstPartyCourse,
    get_first_party_course,
    is_first_party_course_id,
    require_first_party_course,
)

_COMPANION_UUID = "5ddf32c6-e139-4056-ac94-c4a231bfd932"


def test_first_party_companion_identity_is_stable() -> None:
    """Constants must match the canonical companion identity."""
    assert LOGION_MARKETPLACE_COMPANION_SLUG == (
        "logion-marketplace-companion"
    )
    assert LOGION_MARKETPLACE_COMPANION_COURSE_ID == _COMPANION_UUID
    assert LOGION_MARKETPLACE_COMPANION_NAME == (
        "Logion Marketplace Companion"
    )


def test_get_first_party_course_returns_companion() -> None:
    """Slug lookup returns the right FirstPartyCourse."""
    course = get_first_party_course(LOGION_MARKETPLACE_COMPANION_SLUG)
    assert course is not None
    assert isinstance(course, FirstPartyCourse)
    assert course.slug == LOGION_MARKETPLACE_COMPANION_SLUG
    assert course.course_id == _COMPANION_UUID
    assert course.title == LOGION_MARKETPLACE_COMPANION_NAME


def test_get_first_party_course_returns_none_for_unknown() -> None:
    """Unknown slug returns None."""
    assert get_first_party_course("not-a-real-slug") is None


def test_require_first_party_course_raises_for_unknown() -> None:
    """Raises ValueError for unknown slug."""
    with pytest.raises(ValueError, match="unknown first-party course"):
        require_first_party_course("not-a-real-slug")


def test_is_first_party_course_id_true_for_companion_uuid() -> None:
    """True for the companion UUID."""
    assert is_first_party_course_id(_COMPANION_UUID) is True


def test_is_first_party_course_id_false_for_other() -> None:
    """False for non-matching IDs."""
    assert is_first_party_course_id("logion-marketplace-companion") is False
    assert is_first_party_course_id("some-other-uuid") is False
    assert is_first_party_course_id("") is False

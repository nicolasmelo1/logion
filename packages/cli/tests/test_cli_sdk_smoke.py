"""Smoke tests — verify SDK resource class names exist and are importable.

These tests catch typos and renames without constructing a ``LogionClient``,
which avoids relying on lazy ``__init__`` / property-access assumptions that
could break if the SDK ever adds eager validation or network calls.
"""

from __future__ import annotations

from logion.v1 import (
    CourseReviewsResource,
    CoursesResource,
    IdentityResource,
    PaymentsResource,
    ReportsResource,
)


def test_payments_resource_exists() -> None:
    """PaymentsResource class is importable and has expected name."""
    assert PaymentsResource.__name__ == "PaymentsResource"


def test_courses_resource_exists() -> None:
    """CoursesResource class is importable and has expected name."""
    assert CoursesResource.__name__ == "CoursesResource"


def test_identity_resource_exists() -> None:
    """IdentityResource class is importable and has expected name."""
    assert IdentityResource.__name__ == "IdentityResource"


def test_course_reviews_resource_exists() -> None:
    """CourseReviewsResource class is importable and has expected name."""
    assert CourseReviewsResource.__name__ == "CourseReviewsResource"


def test_reports_resource_exists() -> None:
    """ReportsResource class is importable and has expected name."""
    assert ReportsResource.__name__ == "ReportsResource"

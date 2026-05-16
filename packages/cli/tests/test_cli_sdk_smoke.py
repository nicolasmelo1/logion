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
    """PaymentsResource class is importable from SDK."""
    assert issubclass(PaymentsResource, object)


def test_courses_resource_exists() -> None:
    """CoursesResource class is importable from SDK."""
    assert issubclass(CoursesResource, object)


def test_identity_resource_exists() -> None:
    """IdentityResource class is importable from SDK."""
    assert issubclass(IdentityResource, object)


def test_course_reviews_resource_exists() -> None:
    """CourseReviewsResource class is importable from SDK."""
    assert issubclass(CourseReviewsResource, object)


def test_reports_resource_exists() -> None:
    """ReportsResource class is importable from SDK."""
    assert issubclass(ReportsResource, object)

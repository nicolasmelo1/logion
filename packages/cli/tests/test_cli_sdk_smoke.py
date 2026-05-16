"""Smoke tests — verify FakeClient resource names match real SDK types.

These tests catch typos and renames that FakeClient patching would otherwise
mask, since the unit tests never instantiate a real ``LogionClient``.
"""

from __future__ import annotations

from logion import LogionClient


def _v1():
    """Return a real v1 namespace (client created with a dummy key)."""
    return LogionClient(
        base_url="http://localhost",
        api_key="sk-test-dummy-key-for-smoke-test",  # pragma: allowlist secret
    ).v1


def test_real_client_v1_has_payments() -> None:
    """Real LogionClient.v1.payments is a PaymentsResource."""
    res = _v1().payments
    assert type(res).__name__ == "PaymentsResource"


def test_real_client_v1_has_courses() -> None:
    """Real LogionClient.v1.courses is a CoursesResource."""
    res = _v1().courses
    assert type(res).__name__ == "CoursesResource"


def test_real_client_v1_has_identity() -> None:
    """Real LogionClient.v1.identity is an IdentityResource."""
    res = _v1().identity
    assert type(res).__name__ == "IdentityResource"


def test_real_client_v1_has_course_reviews() -> None:
    """Real LogionClient.v1.course_reviews is a CourseReviewsResource."""
    res = _v1().course_reviews
    assert type(res).__name__ == "CourseReviewsResource"


def test_real_client_v1_has_reports() -> None:
    """Real LogionClient.v1.reports is a ReportsResource."""
    res = _v1().reports
    assert type(res).__name__ == "ReportsResource"

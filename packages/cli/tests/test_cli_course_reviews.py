"""Tests for the course-reviews commands."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cli.main import main


class FakeCourseReviewsResource:
    """Fake course_reviews resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

    def list(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("list", kwargs)
        return {"items": [], "next_cursor": None}

    def get(self, review_id: str, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get", {"review_id": review_id, **kwargs})
        return {"id": review_id, "status": "pending"}

    def approve(self, review_id: str, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("approve", {"review_id": review_id, **kwargs})
        return {"id": review_id, "status": "approved"}

    def reject(self, review_id: str, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("reject", {"review_id": review_id, **kwargs})
        return {"id": review_id, "status": "rejected"}


class FakeV1Namespace:
    def __init__(self, course_reviews: FakeCourseReviewsResource) -> None:
        self.course_reviews = course_reviews


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_course_reviews_list(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews list calls SDK."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "list",
        "--limit",
        "10",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "list"
    assert kwargs["limit"] == 10
    data = json.loads(capsys.readouterr().out)
    assert "items" in data


def test_course_reviews_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews get calls SDK."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main(["course-reviews", "get", "r1", "--json"])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "get"
    assert kwargs["review_id"] == "r1"


def test_course_reviews_approve_with_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews approve --yes calls SDK."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "approve",
        "r1",
        "--reviewer-notes",
        "Looks good",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "approve"
    assert kwargs["review_id"] == "r1"
    assert kwargs["reviewer_notes"] == "Looks good"


def test_course_reviews_approve_without_yes() -> None:
    """course-reviews approve without --yes refuses."""
    code = main(["course-reviews", "approve", "r1"])
    assert code == 2


def test_course_reviews_reject_with_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews reject --yes calls SDK."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "reject",
        "r1",
        "--decision-reason",
        "unsafe command",
        "--reviewer-notes",
        "Contains risky command",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "reject"
    assert kwargs["review_id"] == "r1"
    assert kwargs["decision_reason"] == "unsafe command"
    assert kwargs["reviewer_notes"] == "Contains risky command"


def test_course_reviews_reject_without_yes() -> None:
    """course-reviews reject without --yes refuses."""
    code = main([
        "course-reviews",
        "reject",
        "r1",
        "--decision-reason",
        "bad",
        "--reviewer-notes",
        "nope",
    ])
    assert code == 2


def test_course_reviews_approve_empty_id() -> None:
    """course-reviews approve rejects empty review_id."""
    code = main([
        "course-reviews",
        "approve",
        "",
        "--yes",
        "--json",
    ])
    assert code == 2


def test_course_reviews_reject_empty_id() -> None:
    """course-reviews reject rejects empty review_id."""
    code = main([
        "course-reviews",
        "reject",
        "",
        "--decision-reason",
        "bad",
        "--reviewer-notes",
        "nope",
        "--yes",
        "--json",
    ])
    assert code == 2

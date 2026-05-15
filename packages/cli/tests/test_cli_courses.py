"""Tests for the courses commands."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cli.main import main


class FakeCoursesResource:
    """Fake courses resource."""

    def __init__(self) -> None:
        self.last_call: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create", kwargs)
        return {"id": "c1", "title": kwargs["title"], "slug": kwargs["slug"]}

    def get(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get", kwargs)
        return {"id": kwargs["course_id"], "title": "Test Course"}

    def update(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("update", kwargs)
        return {"id": kwargs["course_id"], "updated": True}

    def create_upload_session(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create_upload_session", kwargs)
        return {"version_id": "v1", "files": kwargs["files"]}

    def complete_upload_session(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("complete_upload_session", kwargs)
        return {"status": "completed"}

    def get_version(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_version", kwargs)
        return {"id": kwargs["version_id"]}

    def request_publication_review(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("request_publication_review", kwargs)
        return {"review_id": "r1", "status": "pending"}

    def get_latest_publication_review(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_latest_publication_review", kwargs)
        return {"status": "approved"}

    def review_version(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("review_version", kwargs)
        return {"review_id": "rev1", "rating": kwargs["rating"]}

    def get_my_review(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_my_review", kwargs)
        return {"review_id": "rev1", "rating": 5}

    def list_reviews(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("list_reviews", kwargs)
        return {"items": [], "next_cursor": None}

    def get_review_feedback(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_review_feedback", kwargs)
        return {"feedback": "Looks good"}


class FakeV1Namespace:
    def __init__(self, courses: FakeCoursesResource) -> None:
        self.courses = courses


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_courses_create_calls_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """courses create forwards args to SDK."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "create",
        "--title",
        "RAG",
        "--slug",
        "rag",
        "--tag",
        "python",
        "--tag",
        "agents",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "create"
    assert kwargs["title"] == "RAG"
    assert kwargs["slug"] == "rag"
    assert kwargs["tags"] == ["python", "agents"]
    assert kwargs["description"] is None
    assert kwargs["price_cents"] is None
    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "RAG"


def test_courses_create_all_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses create with all optional args."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "create",
        "--title",
        "RAG",
        "--slug",
        "rag",
        "--description",
        "RAG course",
        "--price-cents",
        "2500",
        "--currency",
        "USD",
        "--language",
        "en",
        "--short-summary",
        "RAG for agents",
        "--visibility",
        "public",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "create"
    assert kwargs["description"] == "RAG course"
    assert kwargs["price_cents"] == 2500
    assert kwargs["currency"] == "USD"
    assert kwargs["language"] == "en"
    assert kwargs["visibility"] == "public"


def test_courses_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses get forwards course_id."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    assert main(["courses", "get", "c1", "--json"]) == 0
    method, kwargs = courses.last_call
    assert method == "get"
    assert kwargs["course_id"] == "c1"


def test_courses_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses update sends only provided fields."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "update",
        "c1",
        "--title",
        "New Title",
        "--price-cents",
        "3000",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "update"
    assert kwargs["course_id"] == "c1"
    assert kwargs["title"] == "New Title"
    assert kwargs["price_cents"] == 3000
    # Omitted fields should NOT appear
    assert "description" not in kwargs
    assert "language" not in kwargs


def test_courses_publication_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses publication request calls SDK."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    assert main(["courses", "publication", "request", "c1", "--json"]) == 0
    method, kwargs = courses.last_call
    assert method == "request_publication_review"
    assert kwargs["course_id"] == "c1"


def test_courses_publication_latest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses publication latest calls SDK."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    assert (
        main([
            "courses",
            "publication",
            "latest",
            "c1",
            "--include-pass",
            "--json",
        ])
        == 0
    )
    method, kwargs = courses.last_call
    assert method == "get_latest_publication_review"
    assert kwargs["course_id"] == "c1"


def test_courses_reviews_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses reviews upsert forwards review fields."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "reviews",
        "upsert",
        "c1",
        "v1",
        "--rating",
        "5",
        "--body",
        "Great course",
        "--completed-task",
        "--reliability",
        "4.5",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "review_version"
    assert kwargs["course_id"] == "c1"
    assert kwargs["version_id"] == "v1"
    assert kwargs["rating"] == 5
    assert kwargs["body"] == "Great course"
    assert kwargs["completed_task"] is True
    assert kwargs["reliability"] == 4.5


def test_courses_reviews_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses reviews list forwards filters."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "reviews",
        "list",
        "c1",
        "--version",
        "latest",
        "--limit",
        "20",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "list_reviews"
    assert kwargs["course_id"] == "c1"
    assert kwargs["version"] == "latest"
    assert kwargs["limit"] == 20


def test_courses_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses feedback calls SDK."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    assert main(["courses", "feedback", "c1", "--json"]) == 0
    method, kwargs = courses.last_call
    assert method == "get_review_feedback"
    assert kwargs["course_id"] == "c1"


def test_courses_create_missing_required() -> None:
    """courses create fails without required args."""
    with pytest.raises(SystemExit):
        main(["courses", "create"])


def test_courses_uploads_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses uploads complete forwards IDs."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "uploads",
        "complete",
        "c1",
        "v1",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "complete_upload_session"
    assert kwargs["course_id"] == "c1"
    assert kwargs["version_id"] == "v1"

"""Tests for the courses commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cli.main import main


class FakeCoursesResource:
    """Fake courses resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

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
    assert "description" not in kwargs
    assert "price_cents" not in kwargs
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


def test_courses_update_with_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses update --tag appends tags."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "update",
        "c1",
        "--tag",
        "python",
        "--tag",
        "ml",
        "--json",
    ])
    assert code == 0
    _method, kwargs = courses.last_call
    assert kwargs["tags"] == ["python", "ml"]


def test_courses_update_clear_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses update --clear-tags sends empty tags list."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "update",
        "c1",
        "--clear-tags",
        "--json",
    ])
    assert code == 0
    _method, kwargs = courses.last_call
    assert kwargs["tags"] == []


def test_courses_uploads_create(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """courses uploads create builds file dicts from paths."""
    f1 = tmp_path / "module1.md"
    f1.write_text("# Module 1\nHello world")
    f2 = tmp_path / "data.json"
    f2.write_text('{"key": "val"}')
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "uploads",
        "create",
        "c1",
        "--file",
        str(f1),
        "--file",
        str(f2),
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "create_upload_session"
    assert kwargs["course_id"] == "c1"
    files = kwargs["files"]
    assert len(files) == 2
    assert files[0]["path"] == str(f1)
    assert files[0]["size_bytes"] == f1.stat().st_size
    assert files[1]["path"] == str(f2)


def test_courses_uploads_create_file_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses uploads create rejects a non-existent file path."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "uploads",
        "create",
        "c1",
        "--file",
        "/no/such/file.md",
        "--json",
    ])
    assert code == 2


def test_courses_uploads_create_no_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses uploads create requires at least one --file."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "uploads",
        "create",
        "c1",
        "--json",
    ])
    assert code == 2


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


def test_courses_reviews_upsert_no_completed_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitting --completed-task means it is not sent to the SDK."""
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
        "4",
        "--json",
    ])
    assert code == 0
    _method, kwargs = courses.last_call
    assert "completed_task" not in kwargs


def test_courses_reviews_upsert_no_completed_task_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--no-completed-task sends completed_task=False to SDK."""
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
        "3",
        "--no-completed-task",
        "--json",
    ])
    assert code == 0
    _method, kwargs = courses.last_call
    assert kwargs["completed_task"] is False


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


def test_courses_reviews_mine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses reviews mine calls SDK."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "reviews",
        "mine",
        "c1",
        "--version-id",
        "v1",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "get_my_review"
    assert kwargs["course_id"] == "c1"
    assert kwargs["version_id"] == "v1"


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


def test_courses_versions_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses versions get calls SDK."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main(["courses", "versions", "get", "c1", "v1", "--json"])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "get_version"
    assert kwargs["course_id"] == "c1"
    assert kwargs["version_id"] == "v1"


def test_courses_create_missing_required() -> None:
    """courses create fails without required args."""
    with pytest.raises(SystemExit):
        main(["courses", "create"])


def test_courses_get_empty_id() -> None:
    """courses get rejects empty course_id."""
    code = main(["courses", "get", "", "--json"])
    assert code == 2


def test_courses_update_empty_id() -> None:
    """courses update rejects empty course_id."""
    code = main(["courses", "update", "", "--title", "X", "--json"])
    assert code == 2

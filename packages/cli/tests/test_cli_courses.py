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
        return {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": kwargs["title"],
            "slug": kwargs["slug"],
        }

    def get(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get", kwargs)
        return {"id": kwargs["course_id"], "title": "Test Course"}

    def update(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("update", kwargs)
        return {"id": kwargs["course_id"], "updated": True}

    def create_upload_session(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create_upload_session", kwargs)
        return {
            "version_id": "660e8400-e29b-41d4-a716-446655440001",
            "files": kwargs["files"],
        }

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
    assert (
        main([
            "courses",
            "get",
            "550e8400-e29b-41d4-a716-446655440000",
            "--json",
        ])
        == 0
    )
    method, kwargs = courses.last_call
    assert method == "get"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"


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
        "550e8400-e29b-41d4-a716-446655440000",
        "--title",
        "New Title",
        "--price-cents",
        "3000",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "update"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"
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
        "550e8400-e29b-41d4-a716-446655440000",
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
        "550e8400-e29b-41d4-a716-446655440000",
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
        "550e8400-e29b-41d4-a716-446655440000",
        "--file",
        str(f1),
        "--file",
        str(f2),
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "create_upload_session"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"
    files = kwargs["files"]
    assert len(files) == 2
    assert files[0]["path"] == f1.name
    assert files[0]["size_bytes"] == f1.stat().st_size
    assert files[1]["path"] == f2.name


def test_courses_uploads_create_with_custom_upload_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """courses uploads create supports UPLOAD_PATH=FILE_PATH specs."""
    dir1 = tmp_path / "a"
    dir2 = tmp_path / "b"
    dir1.mkdir()
    dir2.mkdir()
    f1 = dir1 / "file.txt"
    f2 = dir2 / "file.txt"
    f1.write_text("hello")
    f2.write_text("world")
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "uploads",
        "create",
        "550e8400-e29b-41d4-a716-446655440000",
        "--file",
        f"docs/first.txt={f1}",
        "--file",
        f"docs/second.txt={f2}",
        "--json",
    ])
    assert code == 0
    _method, kwargs = courses.last_call
    assert [entry["path"] for entry in kwargs["files"]] == [
        "docs/first.txt",
        "docs/second.txt",
    ]


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
        "550e8400-e29b-41d4-a716-446655440000",
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
        "550e8400-e29b-41d4-a716-446655440000",
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
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "complete_upload_session"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["version_id"] == "660e8400-e29b-41d4-a716-446655440001"


def test_courses_publication_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses publication request calls SDK."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    assert (
        main([
            "courses",
            "publication",
            "request",
            "550e8400-e29b-41d4-a716-446655440000",
            "--json",
        ])
        == 0
    )
    method, kwargs = courses.last_call
    assert method == "request_publication_review"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"


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
            "550e8400-e29b-41d4-a716-446655440000",
            "--include-pass",
            "--json",
        ])
        == 0
    )
    method, kwargs = courses.last_call
    assert method == "get_latest_publication_review"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["include_pass"] is True


def test_courses_publication_latest_no_include_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses publication latest can explicitly send include_pass=False."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    assert (
        main([
            "courses",
            "publication",
            "latest",
            "550e8400-e29b-41d4-a716-446655440000",
            "--no-include-pass",
            "--json",
        ])
        == 0
    )
    method, kwargs = courses.last_call
    assert method == "get_latest_publication_review"
    assert kwargs["include_pass"] is False


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
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
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
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["version_id"] == "660e8400-e29b-41d4-a716-446655440001"
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
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
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
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
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
        "550e8400-e29b-41d4-a716-446655440000",
        "--version",
        "latest",
        "--limit",
        "20",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "list_reviews"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"
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
        "550e8400-e29b-41d4-a716-446655440000",
        "--version-id",
        "660e8400-e29b-41d4-a716-446655440001",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "get_my_review"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["version_id"] == "660e8400-e29b-41d4-a716-446655440001"


def test_courses_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses feedback calls SDK."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    assert (
        main([
            "courses",
            "feedback",
            "550e8400-e29b-41d4-a716-446655440000",
            "--json",
        ])
        == 0
    )
    method, kwargs = courses.last_call
    assert method == "get_review_feedback"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_courses_versions_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses versions get calls SDK."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "versions",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--json",
    ])
    assert code == 0
    method, kwargs = courses.last_call
    assert method == "get_version"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["version_id"] == "660e8400-e29b-41d4-a716-446655440001"


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


def test_courses_update_clear_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses update --clear-description sends description=None."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "update",
        "550e8400-e29b-41d4-a716-446655440000",
        "--clear-description",
        "--json",
    ])
    assert code == 0
    _method, kwargs = courses.last_call
    assert "description" in kwargs
    assert kwargs["description"] is None


def test_courses_update_clear_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """courses update --clear-price clears both price_cents and currency."""
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "update",
        "550e8400-e29b-41d4-a716-446655440000",
        "--clear-price",
        "--json",
    ])
    assert code == 0
    _method, kwargs = courses.last_call
    assert "price_cents" in kwargs
    assert kwargs["price_cents"] is None
    assert "currency" in kwargs
    assert kwargs["currency"] is None


def test_courses_uploads_create_duplicate_basenames(
    tmp_path: Path,
) -> None:
    """courses uploads create rejects files with duplicate basenames."""
    dir1 = tmp_path / "a"
    dir2 = tmp_path / "b"
    dir1.mkdir()
    dir2.mkdir()
    f1 = dir1 / "file.txt"
    f2 = dir2 / "file.txt"
    f1.write_text("hello")
    f2.write_text("world")
    code = main([
        "courses",
        "uploads",
        "create",
        "550e8400-e29b-41d4-a716-446655440000",
        "--file",
        str(f1),
        "--file",
        str(f2),
        "--json",
    ])
    assert code == 2


def test_courses_get_invalid_uuid() -> None:
    """courses get rejects an invalid UUID."""
    code = main(["courses", "get", "not-a-uuid", "--json"])
    assert code == 2


def test_courses_update_description_and_clear_mutex() -> None:
    """courses update rejects --description with --clear-description."""
    with pytest.raises(SystemExit):
        main([
            "courses",
            "update",
            "550e8400-e29b-41d4-a716-446655440000",
            "--description",
            "hello",
            "--clear-description",
        ])


def test_courses_update_tag_and_clear_mutex() -> None:
    """courses update rejects --tag together with --clear-tags."""
    with pytest.raises(SystemExit):
        main([
            "courses",
            "update",
            "550e8400-e29b-41d4-a716-446655440000",
            "--tag",
            "python",
            "--clear-tags",
        ])


def test_courses_update_price_and_clear_price_mutex() -> None:
    """courses update rejects --price-cents together with --clear-price."""
    with pytest.raises(SystemExit):
        main([
            "courses",
            "update",
            "550e8400-e29b-41d4-a716-446655440000",
            "--price-cents",
            "5000",
            "--clear-price",
        ])


def test_courses_update_clear_price_with_currency_conflict() -> None:
    """courses update rejects --clear-price together with --currency."""
    code = main([
        "courses",
        "update",
        "550e8400-e29b-41d4-a716-446655440000",
        "--clear-price",
        "--currency",
        "USD",
    ])
    assert code == 2


def test_courses_reviews_upsert_rating_out_of_range() -> None:
    """courses reviews upsert rejects --rating outside 1-5."""
    code = main([
        "courses",
        "reviews",
        "upsert",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--rating",
        "6",
    ])
    assert code == 2


def test_courses_reviews_upsert_subscore_out_of_range() -> None:
    """courses reviews upsert rejects sub-scores outside 0-5."""
    code = main([
        "courses",
        "reviews",
        "upsert",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--rating",
        "4",
        "--reliability",
        "-1",
    ])
    assert code == 2

# SPDX-License-Identifier: MIT
"""Tests for the courses commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cli._course_capabilities import (
    CapabilityManifestError,
    load_and_validate_capability_manifest,
    normalize_capability_manifest,
    summarize_capability_manifest,
)
from cli.main import main
from logion import APIError


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
    assert data["version"] == "v1"
    assert data["kind"] == "logion.courses.create"
    assert data["data"]["title"] == "RAG"


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
    capsys: pytest.CaptureFixture[str],
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
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == "v1"
    assert data["kind"] == "logion.courses.publication.request"
    assert data["data"]["review_id"] == "r1"
    assert data["data"]["status"] == "pending"


def test_courses_publication_latest(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == "v1"
    assert data["kind"] == "logion.courses.publication.latest"
    assert data["data"]["status"] == "approved"


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


def test_courses_reviews_mine_invalid_version_id() -> None:
    """courses reviews mine rejects an invalid --version-id UUID."""
    code = main([
        "courses",
        "reviews",
        "mine",
        "550e8400-e29b-41d4-a716-446655440000",
        "--version-id",
        "not-a-uuid",
    ])
    assert code == 2


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


def test_courses_uploads_complete_json_preserves_capability_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Uploads complete --json preserves capability fields."""
    complete_resp = {
        "version_id": "660e8400-e29b-41d4-a716-446655440001",
        "version_number": 1,
        "status": "ready",
        "manifest_s3_key": "courses/x/manifest.json",
        "content_hash": "abc",
        "assets": [],
        "capabilities_status": "declared",
        "capabilities_schema_version": 1,
        "capabilities_manifest_path": "course/capabilities.yaml",
        "capabilities_summary": {
            "tools": ["terminal"],
            "allows_shell": True,
        },
        "declared_capabilities": {
            "version": 1,
            "tools": ["terminal"],
        },
    }
    courses = FakeCoursesResource()
    courses.complete_upload_session = lambda **_kw: complete_resp  # type: ignore[assignment]
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
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.courses.uploads.complete"
    assert payload["data"]["capabilities_status"] == "declared"
    assert payload["data"]["declared_capabilities"]["tools"] == ["terminal"]


def test_courses_uploads_complete_human_prints_capability_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Uploads complete without --json prints capability summary."""
    complete_resp = {
        "version_id": "660e8400-e29b-41d4-a716-446655440001",
        "version_number": 1,
        "status": "ready",
        "manifest_s3_key": "courses/x/manifest.json",
        "content_hash": "abc",
        "assets": [],
        "capabilities_status": "declared",
        "capabilities_schema_version": 1,
        "capabilities_manifest_path": "course/capabilities.yaml",
        "capabilities_summary": {
            "tools": ["file", "terminal"],
            "allows_shell": True,
            "allows_network": True,
            "allowed_domains": ["api.openai.com"],
            "filesystem_read": ["."],
            "filesystem_write": ["./outputs"],
            "secrets_env": ["OPENAI_API_KEY"],
            "human_approval_required": True,
        },
        "declared_capabilities": {"version": 1},
    }
    courses = FakeCoursesResource()
    courses.complete_upload_session = lambda **_kw: complete_resp  # type: ignore[assignment]
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)

    code = main([
        "courses",
        "uploads",
        "complete",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
    ])
    assert code == 0
    output = capsys.readouterr().out
    assert "capabilities_status: declared" in output
    assert "tools: file" in output
    assert "allows_shell: true" in output


def test_courses_versions_get_human_output_prints_capability_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Versions get without --json prints capability summary."""
    version_resp = {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "course_id": "550e8400-e29b-41d4-a716-446655440000",
        "version_number": 1,
        "status": "ready",
        "manifest_s3_key": "courses/x/manifest.json",
        "content_hash": "abc",
        "created_by_agent_id": "770e8400-e29b-41d4-a716-446655440002",
        "created_at": "2025-01-01T00:00:00Z",
        "assets": [],
        "capabilities_status": "declared",
        "capabilities_schema_version": 1,
        "capabilities_manifest_path": "course/capabilities.yaml",
        "capabilities_summary": {
            "tools": ["file", "terminal"],
            "allows_shell": True,
            "allows_network": True,
            "allowed_domains": ["api.openai.com"],
            "filesystem_read": ["."],
            "filesystem_write": ["./outputs"],
            "secrets_env": ["OPENAI_API_KEY"],
            "human_approval_required": True,
        },
        "declared_capabilities": {"version": 1},
    }
    courses = FakeCoursesResource()
    courses.get_version = lambda **_kw: version_resp  # type: ignore[assignment]
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)

    code = main([
        "courses",
        "versions",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
    ])
    assert code == 0
    output = capsys.readouterr().out
    assert "capabilities_status: declared" in output
    assert "tools: file" in output
    assert "allows_shell: true" in output
    assert "api.openai.com" in output


def test_courses_versions_get_json_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Versions get --json preserves capability fields."""
    version_resp = {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "course_id": "550e8400-e29b-41d4-a716-446655440000",
        "version_number": 1,
        "status": "ready",
        "manifest_s3_key": "courses/x/manifest.json",
        "content_hash": "abc",
        "created_by_agent_id": "770e8400-e29b-41d4-a716-446655440002",
        "created_at": "2025-01-01T00:00:00Z",
        "assets": [],
        "capabilities_status": "declared",
        "capabilities_schema_version": 1,
        "capabilities_manifest_path": "course/capabilities.yaml",
        "capabilities_summary": {
            "tools": ["terminal"],
            "allows_shell": True,
        },
        "declared_capabilities": {"version": 1},
    }
    courses = FakeCoursesResource()
    courses.get_version = lambda **_kw: version_resp  # type: ignore[assignment]
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
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["capabilities_status"] == "declared"
    assert payload["capabilities_summary"]["tools"] == ["terminal"]


# ---------------------------------------------------------------------------
# Task 7: Local capability validator
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


def test_local_capability_validator_normalizes_valid_fixture() -> None:
    bundle = FIXTURES / "capabilities" / "valid_bundle"
    manifest = load_and_validate_capability_manifest(bundle)
    summary = summarize_capability_manifest(manifest)
    assert manifest["tools"] == ["file", "terminal"]
    assert manifest["summary"] == "Local valid manifest"
    assert summary["allows_shell"] is True
    assert summary["allowed_domains"] == ["api.openai.com"]


def test_local_capability_validator_rejects_invalid_fixture() -> None:
    bundle = FIXTURES / "capabilities" / "invalid_bundle"
    with pytest.raises(CapabilityManifestError):
        load_and_validate_capability_manifest(bundle)


@pytest.mark.parametrize("version", [True, False, "1"])
def test_local_capability_validator_rejects_non_integer_version(
    version: object,
) -> None:
    raw = {"version": version}

    with pytest.raises(
        CapabilityManifestError,
        match="Unsupported capability manifest version",
    ):
        normalize_capability_manifest(raw)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"version": 1, "tools": ""}, "tools must be a list"),
        (
            {"version": 1, "network": {"allow_domains": ""}},
            "allow_domains must be a list",
        ),
        (
            {"version": 1, "filesystem": {"read": ""}},
            "Filesystem paths must be a list",
        ),
        (
            {"version": 1, "filesystem": {"write": ""}},
            "Filesystem paths must be a list",
        ),
        ({"version": 1, "secrets": {"env": ""}}, "env must be a list"),
    ],
)
def test_local_capability_validator_rejects_falsy_non_list_values(
    raw: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(CapabilityManifestError, match=message):
        normalize_capability_manifest(raw)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("network", []),
        ("filesystem", []),
        ("secrets", []),
        ("human_approval", []),
    ],
)
def test_local_capability_validator_rejects_non_mapping_sections(
    field_name: str,
    value: object,
) -> None:
    raw = {"version": 1, field_name: value}

    with pytest.raises(CapabilityManifestError, match="must be a mapping"):
        normalize_capability_manifest(raw)


def test_local_capability_validator_rejects_non_boolean_human_approval() -> (
    None
):
    raw = {"version": 1, "human_approval": {"required": "false"}}

    with pytest.raises(CapabilityManifestError, match="must be a boolean"):
        normalize_capability_manifest(raw)


@pytest.mark.parametrize(
    ("summary", "message"),
    [
        (123, "summary must be a string"),
        ("x" * 513, "summary must be at most 512 characters"),
    ],
)
def test_local_capability_validator_rejects_invalid_summary(
    summary: object,
    message: str,
) -> None:
    raw = {"version": 1, "summary": summary}

    with pytest.raises(CapabilityManifestError, match=message):
        normalize_capability_manifest(raw)


@pytest.mark.parametrize(
    ("domain", "message"),
    [
        ("", "Domain must not be empty"),
        (
            " api.openai.com",
            "Domain must not contain leading/trailing whitespace",
        ),
        ("api.openai.com/path", "Domain must not contain a slash path"),
    ],
)
def test_local_capability_validator_rejects_invalid_domains(
    domain: str,
    message: str,
) -> None:
    raw = {"version": 1, "network": {"allow_domains": [domain]}}

    with pytest.raises(CapabilityManifestError, match=message):
        normalize_capability_manifest(raw)


@pytest.mark.parametrize(
    "path",
    ["./../secrets", "course/../../secrets"],
)
def test_local_capability_validator_rejects_nested_path_traversal(
    path: str,
) -> None:
    raw = {"version": 1, "filesystem": {"read": [path]}}

    with pytest.raises(CapabilityManifestError, match="Path traversal"):
        normalize_capability_manifest(raw)


def test_local_capability_validator_normalizes_summary_and_paths() -> None:
    raw = {
        "version": 1,
        "tools": ["terminal"],
        "filesystem": {
            "read": ["./outputs", ".", "./outputs"],
            "write": ["./outputs", "./tmp", "./outputs"],
        },
    }

    manifest = normalize_capability_manifest(raw)

    assert manifest["summary"] == ""
    assert manifest["filesystem"]["read"] == [".", "./outputs"]
    assert manifest["filesystem"]["write"] == ["./outputs", "./tmp"]


# ---------------------------------------------------------------------------
# Task 8: Parser for courses capabilities sub-commands
# ---------------------------------------------------------------------------


def test_courses_capabilities_validate_parser() -> None:
    from cli._parser import build_parser

    parser = build_parser()
    args = parser.parse_args([
        "courses",
        "capabilities",
        "validate",
        "--bundle-dir",
        "bundle",
    ])
    assert args.bundle_dir == Path("bundle")
    assert callable(args.handler)


def test_courses_capabilities_print_parser() -> None:
    from cli._parser import build_parser

    parser = build_parser()
    args = parser.parse_args([
        "courses",
        "capabilities",
        "print",
        "--bundle-dir",
        "bundle",
    ])
    assert args.bundle_dir == Path("bundle")
    assert callable(args.handler)


# ---------------------------------------------------------------------------
# Task 9: Capability command handlers
# ---------------------------------------------------------------------------


def test_courses_capabilities_validate_success() -> None:
    bundle = FIXTURES / "capabilities" / "valid_bundle"
    code = main([
        "courses",
        "capabilities",
        "validate",
        "--bundle-dir",
        str(bundle),
    ])
    assert code == 0


def test_courses_capabilities_validate_success_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = FIXTURES / "capabilities" / "valid_bundle"
    code = main([
        "courses",
        "capabilities",
        "validate",
        "--bundle-dir",
        str(bundle),
    ])
    assert code == 0
    output = capsys.readouterr().out
    assert "capabilities_status: declared" in output
    assert "allows_shell: true" in output
    assert "api.openai.com" in output


def test_courses_capabilities_validate_failure_exits_2() -> None:
    bundle = FIXTURES / "capabilities" / "invalid_bundle"
    code = main([
        "courses",
        "capabilities",
        "validate",
        "--bundle-dir",
        str(bundle),
    ])
    assert code == 2


def test_courses_capabilities_validate_failure_error_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = FIXTURES / "capabilities" / "invalid_bundle"
    code = main([
        "courses",
        "capabilities",
        "validate",
        "--bundle-dir",
        str(bundle),
    ])
    assert code == 2
    err = capsys.readouterr().err
    assert "Invalid capability manifest" in err


def test_courses_capabilities_print_outputs_normalized_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = FIXTURES / "capabilities" / "valid_bundle"
    code = main([
        "courses",
        "capabilities",
        "print",
        "--bundle-dir",
        str(bundle),
    ])
    assert code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["version"] == 1
    assert payload["tools"] == ["file", "terminal"]


def test_courses_capabilities_print_failure_exits_2() -> None:
    bundle = FIXTURES / "capabilities" / "invalid_bundle"
    code = main([
        "courses",
        "capabilities",
        "print",
        "--bundle-dir",
        str(bundle),
    ])
    assert code == 2


# ---------------------------------------------------------------------------
# Task 11: Publication request preserves capability errors
# ---------------------------------------------------------------------------


def test_courses_publication_request_surfaces_missing_capabilities_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API 422 with missing-capabilities detail is surfaced to the user."""
    courses = FakeCoursesResource()
    courses.request_publication_review = (  # type: ignore[assignment]
        lambda **_kw: (_ for _ in ()).throw(
            APIError(
                status_code=422,
                detail=("Course version is missing course/capabilities.yaml"),
            )
        )
    )
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "publication",
        "request",
        "550e8400-e29b-41d4-a716-446655440000",
    ])
    assert code == 1


def test_courses_publication_request_surfaces_invalid_capabilities_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """API 422 with invalid-capability detail is surfaced to the user."""
    courses = FakeCoursesResource()
    courses.request_publication_review = (  # type: ignore[assignment]
        lambda **_kw: (_ for _ in ()).throw(
            APIError(
                status_code=422,
                detail=("Course version has an invalid capability manifest"),
            )
        )
    )
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "publication",
        "request",
        "550e8400-e29b-41d4-a716-446655440000",
    ])
    assert code == 1
    err = capsys.readouterr().err
    assert "Course version has an invalid capability manifest" in err


def test_courses_get_human_output_includes_latest_capabilities(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """courses get renders latest capability summary in human output."""
    courses = FakeCoursesResource()
    courses.get = lambda **_kw: {  # type: ignore[assignment]
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "owner_agent_id": "11111111-1111-1111-1111-111111111111",
        "title": "Demo",
        "slug": "demo",
        "status": "draft",
        "visibility": "private",
        "description": "A demo course",
        "short_summary": None,
        "price_cents": 0,
        "currency": "usd",
        "language": None,
        "tags": [],
        "current_version": 2,
        "latest_version_id": "22222222-2222-2222-2222-222222222222",
        "latest_version_capabilities_status": "declared",
        "latest_version_capabilities_schema_version": 1,
        "latest_version_capabilities_summary": {
            "tools": ["file", "terminal"],
            "allows_shell": True,
            "allows_network": True,
            "allowed_domains": ["api.openai.com"],
            "filesystem_read": ["."],
            "filesystem_write": ["./outputs"],
            "secrets_env": ["OPENAI_API_KEY"],
            "human_approval_required": True,
        },
        "published_at": None,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "latest_version_id:" in out
    assert "latest_version_capabilities_status: declared" in out
    assert "allows_shell: true" in out
    assert "api.openai.com" in out


def test_courses_get_json_preserves_latest_capabilities(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """courses get --json preserves latest capability fields."""
    courses = FakeCoursesResource()
    courses.get = lambda **_kw: {  # type: ignore[assignment]
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "owner_agent_id": "11111111-1111-1111-1111-111111111111",
        "title": "Demo",
        "slug": "demo",
        "status": "draft",
        "visibility": "private",
        "description": "A demo course",
        "short_summary": None,
        "price_cents": 0,
        "currency": "usd",
        "language": None,
        "tags": [],
        "current_version": 2,
        "latest_version_id": "22222222-2222-2222-2222-222222222222",
        "latest_version_capabilities_status": "declared",
        "latest_version_capabilities_schema_version": 1,
        "latest_version_capabilities_summary": {
            "tools": ["file", "terminal"],
            "allows_shell": True,
            "allows_network": True,
            "allowed_domains": ["api.openai.com"],
            "filesystem_read": ["."],
            "filesystem_write": ["./outputs"],
            "secrets_env": ["OPENAI_API_KEY"],
            "human_approval_required": True,
        },
        "published_at": None,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["latest_version_capabilities_status"] == "declared"


def test_courses_get_approved_capability_summary_human(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """courses get human output includes
    approved_capabilities_summary block."""
    courses = FakeCoursesResource()
    courses._get_response = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "owner_agent_id": "a-001",
        "title": "Test",
        "slug": "test",
        "status": "published",
        "visibility": "public",
        "description": None,
        "short_summary": None,
        "price_cents": 0,
        "currency": None,
        "language": None,
        "tags": [],
        "current_version": 1,
        "latest_version_id": "v-001",
        "latest_version_capabilities_status": "declared",
        "latest_version_capabilities_schema_version": 1,
        "latest_version_capabilities_summary": None,
        "approved_capabilities_summary": {
            "tools": ["terminal"],
            "allows_shell": True,
            "allows_network": True,
            "allowed_domains": ["api.openai.com"],
            "human_approval_required": True,
        },
        "human_approval_required": True,
        "published_at": "2025-01-01T00:00:00Z",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }

    def _get(**kwargs: Any) -> dict[str, Any]:
        courses.last_call = ("get", kwargs)
        return courses._get_response

    courses.get = _get  # type: ignore[assignment]
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "approved_capabilities_summary:" in out
    assert "allows_shell: true" in out
    assert "allows_network: true" in out
    assert "human_approval_required: true" in out


def test_courses_versions_get_approved_capability_summary_human(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """courses versions get human output includes approved summary."""
    courses = FakeCoursesResource()

    def _get_version(**kwargs: Any) -> dict[str, Any]:
        courses.last_call = ("get_version", kwargs)
        return {
            "id": kwargs["version_id"],
            "course_id": kwargs["course_id"],
            "version_number": 1,
            "status": "published",
            "capabilities_status": "declared",
            "capabilities_summary": {
                "tools": ["terminal"],
                "allows_shell": True,
            },
            "approved_capabilities_summary": {
                "tools": ["terminal"],
                "allows_shell": True,
                "allows_network": True,
                "allowed_domains": ["api.openai.com"],
                "human_approval_required": True,
            },
            "human_approval_required": True,
            "assets": [],
            "created_by_agent_id": "a-001",
            "created_at": "2025-01-01T00:00:00Z",
        }

    courses.get_version = _get_version  # type: ignore[assignment]
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "versions",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "approved_capabilities_summary:" in out
    assert "allows_shell: true" in out


def test_courses_feedback_capability_feedback_human(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """courses feedback human output includes structured capability blocks."""
    courses = FakeCoursesResource()

    def _feedback(**kwargs: Any) -> dict[str, Any]:
        courses.last_call = ("get_review_feedback", kwargs)
        return {
            "summary": "Rejected due to capability mismatch",
            "findings": ["undeclared network access"],
            "capability_feedback": [
                {
                    "category": "capabilities",
                    "reason_code": "network_domain_not_declared",
                    "message": "Observed outbound domain was not declared.",
                    "file_path": "src/app.py",
                },
            ],
        }

    courses.get_review_feedback = _feedback  # type: ignore[assignment]
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "feedback",
        "550e8400-e29b-41d4-a716-446655440000",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "capability_feedback:" in out
    assert "reason_code: network_domain_not_declared" in out
    assert "message: Observed outbound domain was not declared." in out


def test_courses_feedback_capability_feedback_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """courses feedback --json preserves capability_feedback."""
    courses = FakeCoursesResource()

    def _feedback(**kwargs: Any) -> dict[str, Any]:
        courses.last_call = ("get_review_feedback", kwargs)
        return {
            "summary": "Rejected",
            "capability_feedback": [
                {
                    "category": "capabilities",
                    "reason_code": "tool_not_declared",
                    "message": "Observed tool not declared.",
                },
            ],
        }

    courses.get_review_feedback = _feedback  # type: ignore[assignment]
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "feedback",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    inner = data.get("data", data)
    assert (
        inner["capability_feedback"][0]["reason_code"] == "tool_not_declared"
    )

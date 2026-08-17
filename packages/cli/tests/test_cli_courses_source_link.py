# SPDX-License-Identifier: MIT
"""Tests for ``logion courses source-link`` CLI commands."""

from __future__ import annotations

import json

import pytest

from cli._json import JsonObject
from cli.main import main
from logion._errors import ForbiddenError, NotFoundError

CID = "550e8400-e29b-41d4-a716-446655440000"


class FakeCoursesResource:
    def __init__(self) -> None:
        self.last_call: tuple[str, JsonObject] = ("", {})
        self._source_link: JsonObject | None = None
        self.set_error: Exception | None = None
        self.get_error: Exception | None = None
        self.delete_error: Exception | None = None
        self.deleted = False

    def set_source_link(self, **kw: object) -> JsonObject:
        self.last_call = ("set_source_link", kw)
        if self.set_error is not None:
            raise self.set_error
        self._source_link = {
            "course_id": str(kw.get("course_id", CID)),
            "provider": "github",
            "repository": kw.get("repository", ""),
            "default_ref": kw.get("ref", "main"),
            "package_map_path": kw.get("package_map_path")
            or "logion-package-map.yaml",
            "status": "active",
            "github_identity_id": "aaa-bbb-ccc",
        }
        return dict(self._source_link)

    def get_source_link(self, **kw: object) -> JsonObject:
        self.last_call = ("get_source_link", kw)
        if self.get_error is not None:
            raise self.get_error
        if self._source_link is None:
            raise NotFoundError(404, "Source link not found for this course")
        return dict(self._source_link)

    def delete_source_link(self, **kw: object) -> None:
        self.last_call = ("delete_source_link", kw)
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted = True


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


def test_set_calls_sdk_put_and_prints_repository(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "source-link",
        "set",
        CID,
        "--repository",
        "owner/repo",
        "--ref",
        "main",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "repository: owner/repo" in out
    assert "default_ref: main" in out
    assert "status: active" in out
    assert courses.last_call[0] == "set_source_link"
    assert courses.last_call[1]["repository"] == "owner/repo"
    assert courses.last_call[1]["ref"] == "main"


def test_set_json_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main([
        "courses",
        "source-link",
        "set",
        CID,
        "--repository",
        "owner/repo",
        "--json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert '"kind": "logion.courses.source-link.set"' in out
    assert '"repository": "owner/repo"' in out


def test_show_renders_link(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    courses = FakeCoursesResource()
    courses._source_link = {
        "course_id": CID,
        "provider": "github",
        "repository": "owner/repo",
        "default_ref": "main",
        "package_map_path": "logion-package-map.yaml",
        "status": "active",
        "github_identity_id": "aaa-bbb-ccc",
    }
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main(["courses", "source-link", "show", CID])
    assert code == 0
    out = capsys.readouterr().out
    assert "repository: owner/repo" in out
    assert "provider: github" in out


def test_show_404_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main(["courses", "source-link", "show", CID])
    assert code == 1
    err = capsys.readouterr().err
    assert "No source link found" in err


def test_show_404_emits_json_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeClient(v1=FakeV1Namespace(courses=FakeCoursesResource()))
    _patch_client(monkeypatch, fake)

    code = main(["courses", "source-link", "show", CID, "--json"])

    assert code == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["kind"] == "logion.error"
    assert payload["data"]["code"] == "not_found"
    assert payload["data"]["exit_code"] == 1


@pytest.mark.parametrize(
    ("error_attribute", "arguments"),
    [
        (
            "set_error",
            [
                "courses",
                "source-link",
                "set",
                CID,
                "--repository",
                "owner/repo",
                "--json",
            ],
        ),
        (
            "get_error",
            ["courses", "source-link", "show", CID, "--json"],
        ),
        (
            "delete_error",
            [
                "courses",
                "source-link",
                "remove",
                CID,
                "--yes",
                "--json",
            ],
        ),
    ],
)
def test_json_api_failures_use_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error_attribute: str,
    arguments: list[str],
) -> None:
    courses = FakeCoursesResource()
    setattr(
        courses,
        error_attribute,
        ForbiddenError(403, "github_repository_inaccessible"),
    )
    _patch_client(
        monkeypatch,
        FakeClient(v1=FakeV1Namespace(courses=courses)),
    )

    code = main(arguments)

    assert code == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["kind"] == "logion.error"
    assert payload["data"]["code"] == "github_repository_inaccessible"
    assert payload["data"]["exit_code"] == 1


def test_show_does_not_misclassify_non_404_not_found_detail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    courses = FakeCoursesResource()
    courses.get_error = ForbiddenError(403, "Repository not found")
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)

    code = main(["courses", "source-link", "show", CID])

    assert code == 1
    captured = capsys.readouterr()
    assert "No source link found" not in captured.err
    assert "Repository not found" in captured.err


def test_remove_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main(["courses", "source-link", "remove", CID])
    assert code != 0
    assert not courses.deleted


def test_remove_with_yes_calls_delete(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    courses = FakeCoursesResource()
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))
    _patch_client(monkeypatch, fake)
    code = main(["courses", "source-link", "remove", CID, "--yes"])
    assert code == 0
    out = capsys.readouterr().out
    assert "revoked" in out.lower()
    assert courses.last_call[0] == "delete_source_link"
    assert courses.deleted

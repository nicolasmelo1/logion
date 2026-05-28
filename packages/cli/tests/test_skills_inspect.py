"""Tests for the marketplace-aware ``logion skills inspect`` command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from cli._local_state import ensure_layout, write_manifest
from cli.commands.skills._inspect_handler import handle_skills_inspect


def _install_manifest(
    course_id: str,
    version_id: str,
    home: Path,
    overrides: dict[str, Any] | None = None,
) -> None:
    """Write a minimal manifest into home/installed/course_id/version_id."""
    ensure_layout(home)
    manifest: dict[str, Any] = {
        "course_id": course_id,
        "version_id": version_id,
        "title": f"Test {course_id}",
        "source": "logion",
        "installed_at": "2025-01-01T00:00:00Z",
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal", "file"],
        "content_sha256": "abc123",
        "review_status": "approved",
        "entitlement_status": "active",
        "license_scope": "unknown",
        "official_update_channel": True,
        "last_verified_at": "2025-01-01T00:00:00Z",
    }
    if overrides:
        manifest.update(overrides)
    write_manifest(manifest, course_id, version_id, home)


class FakeCoursesResource:
    """Fake courses.get resource."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = data or {}

    def get(self, **_kwargs: Any) -> dict[str, Any]:
        return self._data


class FakeV1Namespace:
    def __init__(self, courses: FakeCoursesResource) -> None:
        self.courses = courses


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def test_skills_inspect_json_shape_matches_envelope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """skills inspect --json emits v1 envelope, kind=logion.skills.inspect."""
    home = tmp_path / "home"
    _install_manifest("test-course", "1.0", home)

    remote_data = {
        "id": "test-course",
        "title": "Test Course (remote)",
        "slug": "test-course",
        "status": "published",
        "description": "Remote description",
    }
    courses = FakeCoursesResource(remote_data)
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))

    args = argparse.Namespace(
        course_id="test-course",
        version_id="1.0",
        target=home,
        json_output=True,
        api_key=None,
        base_url=None,
        timeout=None,
        max_retries=None,
    )
    with (
        patch(
            "cli.commands.skills._inspect_handler.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.skills._inspect_handler.make_client",
            return_value=fake,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=True,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_skills_inspect(args)

    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["version"] == "v1"
    assert data["kind"] == "logion.skills.inspect"
    assert data["data"]["course_id"] == "test-course"
    assert data["data"]["description"] == "Remote description"


def test_skills_inspect_includes_entitlement_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """skills inspect includes entitlement_status from the local manifest."""
    home = tmp_path / "home"
    _install_manifest(
        "ent-course", "2.0", home, {"entitlement_status": "active"}
    )

    courses = FakeCoursesResource({"id": "ent-course"})
    fake = FakeClient(v1=FakeV1Namespace(courses=courses))

    args = argparse.Namespace(
        course_id="ent-course",
        version_id="2.0",
        target=home,
        json_output=True,
        api_key=None,
        base_url=None,
        timeout=None,
        max_retries=None,
    )
    with (
        patch(
            "cli.commands.skills._inspect_handler.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.skills._inspect_handler.make_client",
            return_value=fake,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=True,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_skills_inspect(args)

    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["data"]["entitlement_status"] == "active"


def test_skills_inspect_unsafe_course_id_returns_error(
    tmp_path: Path,
) -> None:
    """skills inspect rejects an unsafe course_id."""
    home = tmp_path / "home"
    ensure_layout(home)

    args = argparse.Namespace(
        course_id="../evil",
        version_id=None,
        target=home,
        json_output=False,
        api_key=None,
        base_url=None,
        timeout=None,
        max_retries=None,
    )
    rc = handle_skills_inspect(args)
    assert rc != 0

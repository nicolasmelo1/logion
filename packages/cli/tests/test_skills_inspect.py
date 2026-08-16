# SPDX-License-Identifier: MIT
"""Tests for the marketplace-aware ``logion skills inspect`` command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from cli._json import JsonObject
from cli._local_state import ensure_layout, write_manifest
from cli.commands.skills._inspect_handler import handle_skills_inspect


def _install_manifest(
    course_id: str,
    version_id: str,
    home: Path,
    overrides: JsonObject | None = None,
) -> None:
    ensure_layout(home)
    manifest: JsonObject = {
        "course_id": course_id,
        "version_id": version_id,
        "title": f"Test {course_id}",
        "source": "logion-marketplace",
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
        "manifest_path": str(
            home / "installed" / course_id / version_id / "manifest.json"
        ),
    }
    if overrides:
        manifest.update(overrides)
    write_manifest(manifest, course_id, version_id, home)


class FakeCoursesResource:
    def __init__(
        self,
        course_data: JsonObject | None = None,
        version_data: JsonObject | None = None,
    ) -> None:
        self._course_data = course_data
        self._version_data = version_data

    def get(self, **_kwargs: object) -> JsonObject:
        if self._course_data is None:
            raise RuntimeError("missing")
        return self._course_data

    def get_version(self, **_kwargs: object) -> JsonObject:
        if self._version_data is None:
            raise RuntimeError("missing")
        return self._version_data


class FakeV1Namespace:
    def __init__(self, courses: FakeCoursesResource) -> None:
        self.courses = courses


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _args(home: Path, **overrides: object) -> argparse.Namespace:
    defaults = {
        "course_id": "test-course",
        "version_id": "1.0.0",
        "verbose": False,
        "target": home,
        "json_output": True,
        "api_key": None,
        "base_url": None,
        "timeout": None,
        "max_retries": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_skills_inspect_json_shape_matches_envelope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    _install_manifest("test-course", "1.0.0", home)
    fake = FakeClient(
        v1=FakeV1Namespace(
            FakeCoursesResource(
                course_data={
                    "id": "test-course",
                    "title": "Remote Title",
                    "description": "Remote description",
                }
            )
        )
    )

    with (
        patch(
            "cli.commands.skills._inspect_handler.make_client",
            return_value=fake,
        ),
        patch("cli.commands.skills._inspect_handler.resolve_config_from_args"),
    ):
        rc = handle_skills_inspect(_args(home))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.skills.inspect"
    assert payload["data"]["course_id"] == "test-course"
    assert payload["data"]["manifest_path"].endswith("manifest.json")
    assert payload["data"]["description"] == "Remote description"


def test_skills_inspect_includes_entitlement_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    _install_manifest(
        "ent-course", "2.0.0", home, {"entitlement_status": "active"}
    )
    fake = FakeClient(
        v1=FakeV1Namespace(
            FakeCoursesResource(course_data={"id": "ent-course"})
        )
    )

    with (
        patch(
            "cli.commands.skills._inspect_handler.make_client",
            return_value=fake,
        ),
        patch("cli.commands.skills._inspect_handler.resolve_config_from_args"),
    ):
        rc = handle_skills_inspect(
            _args(home, course_id="ent-course", version_id="2.0.0")
        )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["entitlement_status"] == "active"


def test_skills_inspect_with_version_id_returns_version_payload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    _install_manifest("versioned-course", "3.0.0", home)
    fake = FakeClient(
        v1=FakeV1Namespace(
            FakeCoursesResource(
                course_data={"id": "versioned-course", "title": "Course"},
                version_data={
                    "id": str(UUID("00000000-0000-0000-0000-000000000123")),
                    "status": "published",
                    "capabilities_manifest_path": "course/capabilities.yaml",
                },
            )
        )
    )

    with (
        patch(
            "cli.commands.skills._inspect_handler.make_client",
            return_value=fake,
        ),
        patch("cli.commands.skills._inspect_handler.resolve_config_from_args"),
    ):
        rc = handle_skills_inspect(
            _args(
                home,
                course_id="versioned-course",
                version_id="3.0.0",
                verbose=True,
            )
        )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["remote_version"]["status"] == "published"
    assert (
        payload["data"]["capabilities_manifest_path"]
        == "course/capabilities.yaml"
    )


def test_skills_inspect_unsafe_course_id_returns_unsafe_identifier_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    rc = handle_skills_inspect(
        _args(home, course_id="../evil", version_id=None, json_output=True)
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["data"]["code"] == "unsafe_identifier"

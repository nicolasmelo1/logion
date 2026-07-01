# SPDX-License-Identifier: MIT
"""Tests for OfficialCompanionService and companion status."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from cli._first_party import LOGION_MARKETPLACE_COMPANION_COURSE_ID
from cli._local_state import ensure_layout, write_manifest
from cli.commands.skills.official import OfficialCompanionService

COMPANION_COURSE_ID = LOGION_MARKETPLACE_COMPANION_COURSE_ID


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return ensure_layout(tmp_path / "logion-test")


def _make_manifest(
    course_id: str = COMPANION_COURSE_ID,
    version_id: str = "v1",
    **overrides: object,
) -> dict:
    base: dict = {
        "course_id": course_id,
        "version_id": version_id,
        "title": "Logion Marketplace Companion",
        "source": "logion-marketplace",
        "installed_at": "2026-01-01T00:00:00Z",
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal"],
        "content_sha256": "0" * 64,
        "review_status": "approved",
        "entitlement_status": "active",
        "license_scope": "unknown",
        "official_update_channel": True,
        "last_verified_at": None,
        "manifest_path": "/tmp/placeholder/manifest.json",
    }
    base.update(overrides)
    return base


def _install_companion(
    home: Path,
    version_id: str = "v1",
    source: str = "logion-marketplace",
) -> None:
    """Write a companion manifest + SKILL.md into *home*."""
    version_dir = home / "installed" / COMPANION_COURSE_ID / version_id
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "SKILL.md").write_text("companion", encoding="utf-8")
    manifest = _make_manifest(
        course_id=COMPANION_COURSE_ID,
        version_id=version_id,
        source=source,
    )
    write_manifest(manifest, COMPANION_COURSE_ID, version_id, home)


def test_companion_status_not_installed(home: Path) -> None:
    """No install → not installed, needs_update=True."""
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    assert not status.installed
    assert status.needs_update
    assert status.reason is not None
    assert status.course_id == COMPANION_COURSE_ID


def test_companion_status_installed(home: Path) -> None:
    """With install → installed=True."""
    _install_companion(home, version_id="v1")
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    assert status.installed
    assert not status.needs_update
    assert status.version_id == "v1"
    assert status.source == "logion-marketplace"


def test_companion_inspect_uses_uuid_course_id(home: Path) -> None:
    """course_id matches the UUID constant."""
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    assert status.course_id == COMPANION_COURSE_ID
    assert len(COMPANION_COURSE_ID) == 36
    assert COMPANION_COURSE_ID.count("-") == 4


def test_companion_install_from_manifest_missing_version(
    home: Path,
) -> None:
    """Manifest without version → reason set."""
    service = OfficialCompanionService(home=home)
    manifest = {"packages": {"logion-companion": {}}}
    status = service.install_from_manifest(manifest)
    assert not status.installed
    assert status.needs_update
    assert status.reason == "Manifest missing companion version"


@pytest.mark.parametrize(
    ("manifest", "reason"),
    [
        ({"packages": []}, "Manifest packages must be an object"),
        (
            {"packages": {"logion-companion": []}},
            "Manifest companion entry must be an object",
        ),
    ],
)
def test_companion_install_from_manifest_malformed_shapes(
    home: Path,
    manifest: dict,
    reason: str,
) -> None:
    service = OfficialCompanionService(home=home)
    status = service.install_from_manifest(manifest)
    assert not status.installed
    assert status.needs_update
    assert status.reason == reason


def test_companion_status_to_dict_has_all_fields(home: Path) -> None:
    """to_dict() has all expected keys."""
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    d = status.to_dict()
    expected_keys = {
        "installed",
        "course_id",
        "version_id",
        "version",
        "source",
        "needs_update",
        "reason",
    }
    assert set(d.keys()) == expected_keys


def _ns(json_output: bool = False) -> argparse.Namespace:
    return argparse.Namespace(json_output=json_output)


def test_handle_companion_status_not_installed(home: Path) -> None:
    """Status handler reports not-installed."""
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    assert not status.installed


def test_handle_companion_install_already_installed(home: Path) -> None:
    """Install handler returns 0 when already installed."""
    _install_companion(home, version_id="v1")
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    assert status.installed


def test_handle_companion_update_not_installed(home: Path) -> None:
    """Update handler returns 1 when not installed."""
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    assert not status.installed


def test_companion_install_from_marketplace(home: Path) -> None:
    """Marketplace install returns a not-installed status."""
    service = OfficialCompanionService(home=home)
    status = service.install_from_marketplace(version_id="v2")
    assert not status.installed
    assert status.source == "marketplace"
    assert status.version_id == "v2"
    assert status.needs_update

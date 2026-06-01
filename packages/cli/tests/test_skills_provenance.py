# SPDX-License-Identifier: MIT
"""Tests for provenance fields and the skills verify subcommand."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from cli._local_state import (
    ensure_layout,
    list_installed,
    read_manifest,
    validate_manifest,
    write_manifest,
)
from cli.commands.skills._verify_handler import handle_skills_verify
from cli.commands.skills.handlers import handle_skills_installed


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return ensure_layout(tmp_path / "logion-test")


def _make_manifest(
    course_id: str = "provenance.skill",
    version_id: str = "2026.05.28",
    title: str = "Provenance Test Skill",
    **overrides: object,
) -> dict:
    base: dict = {
        "course_id": course_id,
        "version_id": version_id,
        "title": title,
        "source": "logion-marketplace",
        "installed_at": "2026-05-28T00:00:00Z",
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal"],
        "content_sha256": "a1b2c3",
        "review_status": "approved",
        "entitlement_status": "active",
        "license_scope": "unknown",
        "official_update_channel": True,
        "last_verified_at": None,
        "manifest_path": "/tmp/placeholder/manifest.json",
    }
    base.update(overrides)
    return base


def _ns(
    target: Path | None = None,
    json_output: bool = False,
    course_id: str | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        target=target, json_output=json_output, course_id=course_id
    )


def test_installed_json_includes_provenance_fields(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = _make_manifest(license_scope="single-buyer")
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )

    rc = handle_skills_installed(_ns(target=home, json_output=True))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    entry = payload["data"][0]
    assert entry["source"] == "logion-marketplace"
    assert entry["license_scope"] == "single-buyer"
    assert entry["manifest_path"].endswith("manifest.json")


def test_marketplace_install_records_source_logion_marketplace(
    home: Path,
) -> None:
    manifest = _make_manifest()
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )
    stored = read_manifest(manifest["course_id"], manifest["version_id"], home)
    assert stored is not None
    assert stored["source"] == "logion-marketplace"


def test_manual_install_records_source_manual(home: Path) -> None:
    manifest = _make_manifest(
        course_id="manual.skill",
        source="manual",
        entitlement_status="unknown",
        official_update_channel=False,
    )
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )
    stored = read_manifest(manifest["course_id"], manifest["version_id"], home)
    assert stored is not None
    assert stored["source"] == "manual"


def test_marketplace_install_records_official_update_channel_true(
    home: Path,
) -> None:
    manifest = _make_manifest()
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )
    stored = read_manifest(manifest["course_id"], manifest["version_id"], home)
    assert stored is not None
    assert stored["official_update_channel"] is True


def test_manual_install_records_official_update_channel_false(
    home: Path,
) -> None:
    manifest = _make_manifest(
        course_id="manual.channel",
        source="manual",
        official_update_channel=False,
        entitlement_status="unknown",
    )
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )
    stored = read_manifest(manifest["course_id"], manifest["version_id"], home)
    assert stored is not None
    assert stored["official_update_channel"] is False


def test_skills_verify_updates_entitlement_status(home: Path) -> None:
    manifest = _make_manifest(entitlement_status="expired")
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )

    rc = handle_skills_verify(_ns(target=home, json_output=True))

    assert rc == 0
    updated = read_manifest(
        manifest["course_id"], manifest["version_id"], home
    )
    assert updated is not None
    assert updated["entitlement_status"] == "expired"


def test_skills_verify_preserves_existing_last_verified_at(
    home: Path,
) -> None:
    manifest = _make_manifest(last_verified_at=None)
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )

    rc = handle_skills_verify(_ns(target=home, json_output=True))

    assert rc == 0
    updated = read_manifest(
        manifest["course_id"], manifest["version_id"], home
    )
    assert updated is not None
    assert updated["last_verified_at"] is None


def test_skills_verify_reports_local_only_verification_mode(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = _make_manifest(last_verified_at=None)
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )

    rc = handle_skills_verify(_ns(target=home, json_output=True))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    entry = payload["data"][0]
    assert entry["verification_mode"] == "local-manifest-only"
    assert entry["source"] == "logion-marketplace"


def test_skills_verify_handles_expired_entitlement_without_crashing(
    home: Path,
) -> None:
    manifest = _make_manifest(entitlement_status="expired")
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )

    rc = handle_skills_verify(_ns(target=home, json_output=False))

    assert rc == 0


def test_validate_manifest_accepts_plan_enums() -> None:
    for source in ("logion-marketplace", "mirror", "manual"):
        for license_scope in ("single-buyer", "team", "open", "unknown"):
            manifest = _make_manifest(
                source=source, license_scope=license_scope
            )
            assert validate_manifest(manifest) == []


def test_list_installed_normalizes_manifest_path(home: Path) -> None:
    manifest = _make_manifest()
    write_manifest(
        manifest, manifest["course_id"], manifest["version_id"], home
    )
    entries = list_installed(home)
    assert entries[0]["manifest_path"].startswith(str(home))

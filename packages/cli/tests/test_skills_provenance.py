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

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


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
        "source": "logion",
        "installed_at": "2026-05-28T00:00:00Z",
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal"],
        "content_sha256": "a1b2c3",
        "review_status": "approved",
        "entitlement_status": "unknown",
        "license_scope": "unknown",
        "official_update_channel": False,
        "last_verified_at": None,
    }
    base.update(overrides)
    return base


def _ns(
    target: Path | None = None,
    json_output: bool = False,
    course_id: str | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        target=target,
        json_output=json_output,
        course_id=course_id,
    )


# ---------------------------------------------------------------------------
# Test 1 - Provenance round-trip
# ---------------------------------------------------------------------------


class TestProvenanceRoundTrip:
    def test_provenance_fields_round_trip(self, home: Path) -> None:
        """Provenance fields survive a manifest write/read cycle."""
        m = _make_manifest(
            entitlement_status="active",
            license_scope="team",
            official_update_channel=True,
            last_verified_at="2026-05-28T12:00:00+00:00",
        )
        write_manifest(m, m["course_id"], m["version_id"], home)
        result = read_manifest(m["course_id"], m["version_id"], home)
        assert result is not None
        assert result["entitlement_status"] == "active"
        assert result["license_scope"] == "team"
        assert result["official_update_channel"] is True
        assert result["last_verified_at"] == "2026-05-28T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Test 2 - validate_manifest rejects bad provenance
# ---------------------------------------------------------------------------


class TestProvenanceValidation:
    def test_invalid_entitlement_status(self) -> None:
        m = _make_manifest(entitlement_status="bogus")
        errors = validate_manifest(m)
        assert any("entitlement_status" in e for e in errors)

    def test_invalid_license_scope(self) -> None:
        m = _make_manifest(license_scope="nonsense")
        errors = validate_manifest(m)
        assert any("license_scope" in e for e in errors)

    def test_valid_provenance_fields(self) -> None:
        """All valid enum values should pass validation."""
        for es in ("active", "missing", "expired", "unknown"):
            for ls in ("single_buyer", "team", "open", "unknown"):
                m = _make_manifest(
                    entitlement_status=es,
                    license_scope=ls,
                )
                assert validate_manifest(m) == [], (
                    f"error for es={es}, ls={ls}"
                )


# ---------------------------------------------------------------------------
# Test 3 - list_installed preserves provenance fields
# ---------------------------------------------------------------------------


class TestProvenanceInList:
    def test_list_installed_preserves_provenance(self, home: Path) -> None:
        m = _make_manifest(
            entitlement_status="active",
            license_scope="open",
            official_update_channel=True,
            last_verified_at="2026-01-01T00:00:00Z",
        )
        write_manifest(m, m["course_id"], m["version_id"], home)
        installed = list_installed(home)
        assert len(installed) == 1
        entry = installed[0]
        assert entry["entitlement_status"] == "active"
        assert entry["license_scope"] == "open"
        assert entry["official_update_channel"] is True
        assert entry["last_verified_at"] == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Test 4 - skills verify updates provenance
# ---------------------------------------------------------------------------


class TestSkillsVerifyUpdatesProvenance:
    def test_verify_sets_active_and_timestamp(self, home: Path) -> None:
        """Verify updates entitlement_status and last_verified_at."""
        m = _make_manifest(
            entitlement_status="unknown",
            last_verified_at=None,
        )
        write_manifest(m, m["course_id"], m["version_id"], home)

        rc = handle_skills_verify(_ns(target=home, json_output=True))
        assert rc == 0

        updated = read_manifest(m["course_id"], m["version_id"], home)
        assert updated is not None
        assert updated["entitlement_status"] == "active"
        assert updated["last_verified_at"] is not None
        assert len(updated["last_verified_at"]) > 0

    def test_verify_with_course_id_filter(self, home: Path) -> None:
        """Verify --course-id only verifies matching skills."""
        m1 = _make_manifest(
            course_id="alpha.skill",
            version_id="1.0",
            entitlement_status="unknown",
        )
        m2 = _make_manifest(
            course_id="beta.skill",
            version_id="1.0",
            entitlement_status="unknown",
        )
        write_manifest(m1, "alpha.skill", "1.0", home)
        write_manifest(m2, "beta.skill", "1.0", home)

        rc = handle_skills_verify(
            _ns(
                target=home,
                json_output=True,
                course_id="alpha.skill",
            )
        )
        assert rc == 0

        alpha = read_manifest("alpha.skill", "1.0", home)
        beta = read_manifest("beta.skill", "1.0", home)
        assert alpha is not None
        assert alpha["entitlement_status"] == "active"
        assert beta is not None
        assert beta["entitlement_status"] == "unknown"


# ---------------------------------------------------------------------------
# Test 5 - skills verify with no installed skills
# ---------------------------------------------------------------------------


class TestSkillsVerifyEmpty:
    def test_verify_no_skills_returns_zero(
        self,
        home: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When no skills installed, verify prints a message and exits 0."""
        rc = handle_skills_verify(_ns(target=home, json_output=False))
        assert rc == 0
        assert "No installed skills" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Test 6 - skills installed shows provenance fields
# ---------------------------------------------------------------------------


class TestSkillsInstalledProvenance:
    def test_installed_shows_provenance_via_json(
        self,
        home: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """handle_skills_installed --json includes provenance."""
        m = _make_manifest(
            entitlement_status="expired",
            license_scope="single_buyer",
        )
        write_manifest(m, m["course_id"], m["version_id"], home)

        rc = handle_skills_installed(_ns(target=home, json_output=True))
        assert rc == 0

        output = capsys.readouterr().out
        payload = json.loads(output)
        data = payload["data"]
        assert len(data) == 1
        assert data[0]["entitlement_status"] == "expired"
        assert data[0]["license_scope"] == "single_buyer"

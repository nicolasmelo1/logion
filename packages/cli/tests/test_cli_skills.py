# SPDX-License-Identifier: MIT
"""Tests for the ``logion skills`` command group."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.main import main


def _make_source_bundle(root: Path) -> Path:
    """Create a minimal valid skill bundle under *root*."""
    src = root / "src-bundle"
    (src / "course").mkdir(parents=True)
    (src / "references").mkdir()
    (src / "SKILL.md").write_text(
        "---\nname: test\n---\n# Test Skill\n", encoding="utf-8"
    )
    (src / "course" / "capabilities.yaml").write_text(
        "version: 1\nsummary: test\ntools:\n  - file\n",
        encoding="utf-8",
    )
    (src / "references" / "x.md").write_text("ref", encoding="utf-8")
    return src


class TestSkillsInstall:
    def test_install_writes_manifest_and_indexes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        bundle = _make_source_bundle(tmp_path)
        rc = main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "weather.basic",
            "--version-id",
            "1.0.0",
            "--target",
            str(home),
        ])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Installed:" in captured.out
        assert (
            home / "installed" / "weather.basic" / "1.0.0" / "manifest.json"
        ).is_file()
        assert (home / "index.json").is_file()
        assert (home / "recall.json").is_file()

    def test_install_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        bundle = _make_source_bundle(tmp_path)
        rc = main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "weather.basic",
            "--version-id",
            "1.0.0",
            "--target",
            str(home),
            "--dry-run",
        ])
        assert rc == 0
        assert not (home / "installed").exists() or not any(
            (home / "installed").rglob("manifest.json")
        )

    def test_install_refuses_conflicting_content(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        bundle = _make_source_bundle(tmp_path)
        rc1 = main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "x",
            "--version-id",
            "1.0",
            "--target",
            str(home),
        ])
        assert rc1 == 0
        (bundle / "SKILL.md").write_text("changed", encoding="utf-8")
        rc2 = main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "x",
            "--version-id",
            "1.0",
            "--target",
            str(home),
        ])
        captured = capsys.readouterr()
        assert rc2 == 2
        assert "different content" in captured.err


class TestSkillsInstalled:
    def test_installed_lists_manifests(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        bundle = _make_source_bundle(tmp_path)
        main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "x",
            "--version-id",
            "1.0",
            "--target",
            str(home),
        ])
        capsys.readouterr()
        rc = main(["skills", "installed", "--target", str(home)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "x/1.0" in captured.out

    def test_installed_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        bundle = _make_source_bundle(tmp_path)
        main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "x",
            "--version-id",
            "1.0",
            "--target",
            str(home),
        ])
        capsys.readouterr()
        rc = main(["skills", "installed", "--target", str(home), "--json"])
        captured = capsys.readouterr()
        assert rc == 0
        data = json.loads(captured.out)
        assert data["data"][0]["course_id"] == "x"


class TestSkillsUpdates:
    def test_updates_flags_local_modification(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        bundle = _make_source_bundle(tmp_path)
        main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "x",
            "--version-id",
            "1.0",
            "--target",
            str(home),
        ])
        capsys.readouterr()
        installed_skill = home / "installed" / "x" / "1.0" / "SKILL.md"
        installed_skill.write_text("user changed this", encoding="utf-8")
        rc = main(["skills", "updates", "--target", str(home)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "locally-modified" in captured.out


class TestSkillsUpdate:
    def test_update_refuses_locally_modified_without_force(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        bundle = _make_source_bundle(tmp_path)
        main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "x",
            "--version-id",
            "1.0",
            "--target",
            str(home),
        ])
        capsys.readouterr()
        (home / "installed" / "x" / "1.0" / "SKILL.md").write_text(
            "user changed", encoding="utf-8"
        )
        # Build a new source bundle to update from
        new_bundle = _make_source_bundle(tmp_path / "new")
        (new_bundle / "SKILL.md").write_text("v2 contents", encoding="utf-8")
        rc = main([
            "skills",
            "update",
            "x",
            "--version-id",
            "1.0",
            "--source",
            str(new_bundle),
            "--target",
            str(home),
        ])
        captured = capsys.readouterr()
        assert rc == 2
        assert "user modification detected" in captured.err

    def test_update_force_overwrites(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        bundle = _make_source_bundle(tmp_path)
        main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "x",
            "--version-id",
            "1.0",
            "--target",
            str(home),
        ])
        capsys.readouterr()
        new_bundle = _make_source_bundle(tmp_path / "new")
        (new_bundle / "SKILL.md").write_text("v2 contents", encoding="utf-8")
        rc = main([
            "skills",
            "update",
            "x",
            "--version-id",
            "1.0",
            "--source",
            str(new_bundle),
            "--target",
            str(home),
            "--force",
        ])
        assert rc == 0
        body = (home / "installed" / "x" / "1.0" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert body == "v2 contents"


class TestSkillsInspect:
    def test_inspect_returns_manifest_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        bundle = _make_source_bundle(tmp_path)
        main([
            "skills",
            "install",
            "--source",
            str(bundle),
            "--course-id",
            "x",
            "--version-id",
            "1.0",
            "--target",
            str(home),
        ])
        capsys.readouterr()
        rc = main(["skills", "inspect", "x", "--target", str(home), "--json"])
        captured = capsys.readouterr()
        assert rc == 0
        data = json.loads(captured.out)
        assert data["data"]["course_id"] == "x"

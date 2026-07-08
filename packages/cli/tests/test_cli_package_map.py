# SPDX-License-Identifier: MIT
"""Tests for ``logion courses package-map`` (validate + init)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._package_map import PACKAGE_MAP_FILENAME
from cli.main import main

_INIT_KIND = "logion.courses.package-map.init"
_VALIDATE_KIND = "logion.courses.package-map.validate"


def _write_skill(
    root: Path, slug: str, name: str, description: str = "d"
) -> None:
    d = root / "skills" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nBody.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def test_init_json_emits_result_without_writing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_skill(tmp_path, "hello", "hello")
    code = main([
        "courses",
        "package-map",
        "init",
        "--dir",
        str(tmp_path),
        "--json",
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == _INIT_KIND
    data = payload["data"]
    assert data["source"] == "skill_scan"
    assert data["components"][0]["name"] == "hello"
    assert data["package_map"]["version"] == 1
    # --json must not write a file.
    assert not (tmp_path / PACKAGE_MAP_FILENAME).exists()


def test_init_writes_with_yes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_skill(tmp_path, "hello", "hello")
    code = main([
        "courses",
        "package-map",
        "init",
        "--dir",
        str(tmp_path),
        "--slug",
        "hello-pkg",
        "--yes",
    ])
    assert code == 0
    capsys.readouterr()
    out_file = tmp_path / PACKAGE_MAP_FILENAME
    assert out_file.exists()
    assert "slug: hello-pkg" in out_file.read_text(encoding="utf-8")


def test_init_refuses_overwrite(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_skill(tmp_path, "hello", "hello")
    (tmp_path / PACKAGE_MAP_FILENAME).write_text(
        "version: 1\n", encoding="utf-8"
    )
    code = main(["courses", "package-map", "init", "--dir", str(tmp_path)])
    assert code == 1
    assert "already exists" in capsys.readouterr().err


def test_init_exit_2_on_unresolved_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # No LICENSE → a no_license review flag; without --yes this blocks.
    _write_skill(tmp_path, "hello", "hello")
    code = main(["courses", "package-map", "init", "--dir", str(tmp_path)])
    assert code == 2
    out = capsys.readouterr()
    assert "need review" in out.out
    assert not (tmp_path / PACKAGE_MAP_FILENAME).exists()


def test_init_json_refuse_overwrite_envelope(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / PACKAGE_MAP_FILENAME).write_text(
        "version: 1\n", encoding="utf-8"
    )
    code = main([
        "courses",
        "package-map",
        "init",
        "--dir",
        str(tmp_path),
        "--json",
    ])
    assert code == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["kind"] == "logion.error"
    assert payload["data"]["code"] == "map_already_exists"


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_clean_map(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / PACKAGE_MAP_FILENAME).write_text(
        "version: 1\n"
        "package:\n  slug: p\n"
        "components:\n"
        "  capabilities:\n"
        "    core:\n"
        "      entrypoint: skills/core/SKILL.md\n"
        "      include: ['skills/core/**']\n",
        encoding="utf-8",
    )
    code = main([
        "courses",
        "package-map",
        "validate",
        "--dir",
        str(tmp_path),
        "--json",
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == _VALIDATE_KIND
    assert payload["data"]["valid"] is True


def test_validate_missing_map(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["courses", "package-map", "validate", "--dir", str(tmp_path)])
    assert code == 1
    assert "no logion-package-map.yaml" in capsys.readouterr().err


def test_validate_reports_warnings(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / PACKAGE_MAP_FILENAME).write_text(
        "version: 2\npackage:\n  slug: p\nbogus: true\n",
        encoding="utf-8",
    )
    code = main([
        "courses",
        "package-map",
        "validate",
        "--dir",
        str(tmp_path),
        "--json",
    ])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    codes = {w["code"] for w in payload["data"]["warnings"]}
    assert "package_map_unsupported_version" in codes
    assert "package_map_unknown_keys" in codes
    assert payload["data"]["valid"] is False

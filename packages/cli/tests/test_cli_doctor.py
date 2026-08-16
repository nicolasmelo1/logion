# SPDX-License-Identifier: MIT
"""Tests for the ``logion doctor`` command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from cli._version import __version__
from cli.commands import doctor


def _run(json_output: bool = False) -> int:
    return doctor.handle_doctor(argparse.Namespace(json_output=json_output))


def test_doctor_reports_authoritative_version_when_clean(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    monkeypatch.setattr(doctor.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(doctor, "MARKER_PATH", tmp_path / "absent-marker.json")
    monkeypatch.setattr(doctor, "MANAGED_VENV_DIR", tmp_path / "no-venv")

    data = doctor._collect()

    assert data["cli_version"] == __version__
    assert data["install_method"] == "other"
    assert data["npm_marker"] is None
    assert data["installed_courses"] == 0
    assert data["warnings"] == []
    assert data["ok"] is True
    assert _run() == 0
    assert __version__ in capsys.readouterr().out


def test_doctor_flags_stale_npm_marker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    venv = tmp_path / "npm-managed-venv"
    venv.mkdir()
    marker = tmp_path / "npm-wrapper-installer.json"
    marker.write_text(
        json.dumps({
            "installer": "venv",
            "version": "0.0.1-old",
            "installedAt": "x",
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor, "MARKER_PATH", marker)
    monkeypatch.setattr(doctor, "MANAGED_VENV_DIR", venv)
    monkeypatch.setattr(doctor.sys, "executable", str(venv / "bin" / "python"))

    data = doctor._collect()

    assert data["install_method"] == "npm-managed-venv"
    assert data["managed_venv_present"] is True
    assert data["ok"] is False
    assert any("0.0.1-old" in w for w in data["warnings"])


def test_doctor_detects_pipx_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    monkeypatch.setattr(doctor, "MARKER_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(doctor, "MANAGED_VENV_DIR", tmp_path / "no-venv")
    monkeypatch.setattr(
        doctor.sys,
        "executable",
        "/home/u/.local/pipx/venvs/logion-cli/bin/python",
    )

    assert doctor._collect()["install_method"] == "pipx"


def test_doctor_json_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    monkeypatch.setattr(doctor.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(doctor, "MARKER_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(doctor, "MANAGED_VENV_DIR", tmp_path / "no-venv")

    assert _run(json_output=True) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.doctor"
    assert payload["data"]["cli_version"] == __version__

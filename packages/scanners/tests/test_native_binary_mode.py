# SPDX-License-Identifier: MIT
"""Unit tests for the native-binary execution mode of the Docker-backed
scanners (trivy, osv).

These do not require Docker — they mock ``subprocess.run`` to assert the
command is built against the native binary (no ``docker run`` wrapper, no
bind mount) and that a missing binary surfaces a clear error.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from logion_scanners.adapters.osv import OsvScanner
from logion_scanners.adapters.trivy import TrivyScanner
from logion_scanners.models import SCANNER_OSV, SCANNER_TRIVY


class _FakeProc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_trivy_native_builds_binary_command(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return _FakeProc(0, stdout=json.dumps({"Results": []}))

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = TrivyScanner(binary_path="trivy").scan(tmp_path)

    assert captured["cmd"][0] == "trivy"
    assert "docker" not in captured["cmd"]
    assert "-v" not in captured["cmd"]  # no bind mount in native mode
    assert captured["cmd"][-1] == str(tmp_path.resolve())
    assert result.layer == SCANNER_TRIVY
    assert result.error is None
    assert result.passed is True


def test_osv_native_builds_binary_command(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return _FakeProc(0, stdout=json.dumps({"results": []}))

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = OsvScanner(binary_path="osv-scanner").scan(tmp_path)

    assert captured["cmd"][0] == "osv-scanner"
    assert "docker" not in captured["cmd"]
    assert "-v" not in captured["cmd"]
    assert captured["cmd"][-1] == str(tmp_path.resolve())
    assert result.layer == SCANNER_OSV
    assert result.error is None
    assert result.passed is True


def test_default_mode_still_uses_docker(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return _FakeProc(0, stdout=json.dumps({"Results": []}))

    monkeypatch.setattr(subprocess, "run", fake_run)

    TrivyScanner().scan(tmp_path)

    assert captured["cmd"][0] == "docker"
    assert "run" in captured["cmd"]


@pytest.mark.parametrize(
    ("scanner", "layer", "needle"),
    [
        (
            TrivyScanner(binary_path="/no/such/trivy"),
            SCANNER_TRIVY,
            "Trivy binary not found",
        ),
        (
            OsvScanner(binary_path="/no/such/osv"),
            SCANNER_OSV,
            "OSV-Scanner binary not found",
        ),
    ],
)
def test_missing_native_binary_reports_clear_error(
    monkeypatch, tmp_path, scanner, layer, needle
):
    def fake_run(cmd, **_kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = scanner.scan(tmp_path)

    assert result.layer == layer
    assert result.passed is False
    assert result.error is not None
    assert needle in result.error
    assert "Docker" not in result.error  # native mode must not blame Docker


def test_osv_native_no_packages_passes(monkeypatch, tmp_path):
    """osv-scanner exit 128 (no manifests) is a clean pass in native mode."""

    def fake_run(_cmd, **_kwargs):
        return _FakeProc(128, stdout="", stderr="no packages")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = OsvScanner(binary_path="osv-scanner").scan(tmp_path)

    assert result.passed is True
    assert result.error is None
    assert result.findings == []

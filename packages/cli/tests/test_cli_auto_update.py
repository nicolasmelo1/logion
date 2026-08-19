# SPDX-License-Identifier: MIT
"""Tests for persistent CLI auto-update policy."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cli import _auto_update
from cli._json import JsonObject
from cli.main import main


def test_auto_update_counts_commands_persistently(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    args = argparse.Namespace(command="docs")

    _auto_update.maybe_auto_update(args)
    _auto_update.maybe_auto_update(args)

    data = json.loads((tmp_path / "auto_update.json").read_text())
    assert data["enabled"] is True
    assert data["command_count"] == 2
    assert data["commands_since_check"] == 2


def test_auto_update_runs_when_command_threshold_is_reached(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    # This suite runs from a checkout; opt out of the editable skip
    # so the update path under test is reachable.
    monkeypatch.setattr(_auto_update, "_is_editable_install", lambda: False)
    monkeypatch.setattr(_auto_update, "DEFAULT_COMMAND_THRESHOLD", 2)
    calls: list[argparse.Namespace] = []

    def fake_run(args: argparse.Namespace) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(["sh"], 0, "", "")

    monkeypatch.setattr(_auto_update, "_run_update", fake_run)
    args = argparse.Namespace(command="docs")

    _auto_update.maybe_auto_update(args)
    _auto_update.maybe_auto_update(args)

    assert len(calls) == 1
    data = json.loads((tmp_path / "auto_update.json").read_text())
    assert data["commands_since_check"] == 0
    assert data["last_success_at"]


def test_auto_update_runs_when_last_check_is_stale(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    # This suite runs from a checkout; opt out of the editable skip
    # so the update path under test is reachable.
    monkeypatch.setattr(_auto_update, "_is_editable_install", lambda: False)
    stale = datetime.now(UTC) - timedelta(
        hours=_auto_update.DEFAULT_INTERVAL_HOURS + 1
    )
    (tmp_path / "auto_update.json").write_text(
        json.dumps({
            "schema_version": 1,
            "enabled": True,
            "last_checked_at": stale.isoformat(),
        }),
        encoding="utf-8",
    )
    calls: list[argparse.Namespace] = []

    def fake_run(args: argparse.Namespace) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(["sh"], 0, "", "")

    monkeypatch.setattr(_auto_update, "_run_update", fake_run)

    _auto_update.maybe_auto_update(argparse.Namespace(command="docs"))

    assert len(calls) == 1


def test_auto_update_skips_an_editable_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An editable install must never be replaced by a published release.

    Replacing it is not an update, it is a silent downgrade to a different
    CLI — and it removes the very commands a dev install exists to exercise.
    """
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    monkeypatch.setattr(_auto_update, "DEFAULT_COMMAND_THRESHOLD", 1)
    monkeypatch.setattr(_auto_update, "_is_editable_install", lambda: True)
    calls: list[argparse.Namespace] = []

    def fake_run(args: argparse.Namespace) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(["sh"], 0, "", "")

    monkeypatch.setattr(_auto_update, "_run_update", fake_run)

    _auto_update.maybe_auto_update(argparse.Namespace(command="docs"))

    assert calls == []
    state = json.loads((tmp_path / "auto_update.json").read_text())
    assert "editable install" in state["last_skip_reason"]


def test_editable_install_detected_from_outside_site_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detection is by import location, not by install method.

    A checkout path is outside the interpreter's ``purelib``; a normal
    install is inside it. That distinction holds for pip -e, pipx
    --editable and uv tool --editable alike.
    """
    monkeypatch.setattr(
        _auto_update.sysconfig,
        "get_paths",
        lambda: {"purelib": "/nowhere/site-packages"},
    )
    assert _auto_update._is_editable_install() is True

    real_parent = Path(_auto_update.__file__).resolve().parent.parent
    monkeypatch.setattr(
        _auto_update.sysconfig,
        "get_paths",
        lambda: {"purelib": str(real_parent)},
    )
    assert _auto_update._is_editable_install() is False


def test_auto_update_skips_npm_managed_venv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    monkeypatch.setattr(_auto_update, "DEFAULT_COMMAND_THRESHOLD", 1)
    managed_python = (
        Path.home() / ".logion" / "npm-managed-venv" / "bin" / "python"
    )
    monkeypatch.setattr(_auto_update.sys, "executable", str(managed_python))
    calls: list[argparse.Namespace] = []

    def fake_run(args: argparse.Namespace) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(["sh"], 0, "", "")

    monkeypatch.setattr(_auto_update, "_run_update", fake_run)

    _auto_update.maybe_auto_update(argparse.Namespace(command="docs"))

    assert calls == []
    data = json.loads((tmp_path / "auto_update.json").read_text())
    assert data["commands_since_check"] == 1
    # A skip is recorded under last_skip_reason, not last_error.
    assert "npm-managed install" in data["last_skip_reason"]
    assert data.get("last_error") is None


def test_auto_update_skips_when_state_is_not_writable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOGION_AUTO_UPDATE", raising=False)
    monkeypatch.setattr(_auto_update, "DEFAULT_COMMAND_THRESHOLD", 1)
    calls: list[argparse.Namespace] = []

    def fail_write(
        _data: JsonObject,
        _home: Path | None = None,
    ) -> None:
        raise PermissionError("state directory is not writable")

    def fake_run(args: argparse.Namespace) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(["sh"], 0, "", "")

    monkeypatch.setattr(_auto_update, "_write_state", fail_write)
    monkeypatch.setattr(_auto_update, "_run_update", fake_run)

    _auto_update.maybe_auto_update(argparse.Namespace(command="docs"))

    assert calls == []


def test_auto_update_env_disable_does_not_write_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGION_AUTO_UPDATE", "0")

    def fail_write(
        _data: JsonObject,
        _home: Path | None = None,
    ) -> None:
        raise AssertionError("disabled auto-update should not write state")

    monkeypatch.setattr(_auto_update, "_write_state", fail_write)

    _auto_update.maybe_auto_update(argparse.Namespace(command="docs"))


def test_update_can_disable_auto_update(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))

    code = main(["update", "--disable-auto-update", "--json"])

    assert code == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["enabled"] is False
    assert _auto_update.is_enabled() is False

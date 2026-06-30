# SPDX-License-Identifier: MIT
"""Tests for persistent CLI auto-update policy."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cli import _auto_update
from cli.main import main


def test_auto_update_counts_commands_persistently(
    monkeypatch: Any,
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
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
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
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
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


def test_auto_update_skips_npm_managed_venv(
    monkeypatch: Any,
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
    assert "npm-managed install" in data["last_error"]


def test_update_can_disable_auto_update(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))

    code = main(["update", "--disable-auto-update", "--json"])

    assert code == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["enabled"] is False
    assert _auto_update.is_enabled() is False

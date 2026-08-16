# SPDX-License-Identifier: MIT
"""Persistent CLI auto-update policy."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cli._json import JsonObject, opt_int
from cli._local_state import _atomic_write_text, get_home

STATE_FILENAME = "auto_update.json"
DEFAULT_COMMAND_THRESHOLD = 25
DEFAULT_INTERVAL_HOURS = 24
NPM_MANAGED_VENV_DIRNAME = "npm-managed-venv"


def state_path(home: Path | None = None) -> Path:
    """Return the persisted auto-update state path."""
    return (home or get_home()) / STATE_FILENAME


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _read_state(home: Path | None = None) -> JsonObject:
    path = state_path(home)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_state(data: JsonObject, home: Path | None = None) -> None:
    path = state_path(home)
    data["schema_version"] = 1
    _atomic_write_text(
        path,
        json.dumps(data, indent=2, sort_keys=True) + "\n",
    )
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def _try_write_state(data: JsonObject, home: Path | None = None) -> bool:
    """Best-effort state write for automatic update bookkeeping."""
    try:
        _write_state(data, home)
    except OSError:
        return False
    return True


def is_enabled(home: Path | None = None) -> bool:
    """Return whether auto-update is enabled."""
    return bool(_read_state(home).get("enabled", True))


def set_enabled(enabled: bool, home: Path | None = None) -> JsonObject:
    """Persist the auto-update enabled flag."""
    data = _read_state(home)
    data["enabled"] = enabled
    _write_state(data, home)
    return data


def status(home: Path | None = None) -> JsonObject:
    """Return a stable auto-update status payload."""
    data = _read_state(home)
    return {
        "enabled": data.get("enabled", True),
        "command_count": int(opt_int(data, "command_count", 0) or 0),
        "commands_since_check": int(
            opt_int(data, "commands_since_check", 0) or 0
        ),
        "last_checked_at": data.get("last_checked_at"),
        "last_attempt_at": data.get("last_attempt_at"),
        "last_success_at": data.get("last_success_at"),
        "last_error": data.get("last_error"),
        "last_skip_reason": data.get("last_skip_reason"),
        "command_threshold": DEFAULT_COMMAND_THRESHOLD,
        "interval_hours": DEFAULT_INTERVAL_HOURS,
    }


def _is_npm_managed_python() -> bool:
    """Return True when this CLI is running from the npm wrapper venv.

    The npm wrapper shim always dispatches into the managed venv
    (``~/.logion/npm-managed-venv/bin/logion`` on POSIX,
    ``...\\Scripts\\logion.exe`` on Windows).  That environment is managed by
    npm postinstall, not by the curl installer used for Python CLI updates.  If
    auto-update runs here, the generic installer can update pipx/uv while the
    npm shim keeps invoking the stale managed venv.
    """
    executable = Path(sys.executable).expanduser().absolute()
    managed = (Path.home() / ".logion" / NPM_MANAGED_VENV_DIRNAME).absolute()
    # sys.executable is the interpreter *inside* the venv, so it lives under
    # the managed dir — a parent-membership test is the meaningful check.
    return managed in executable.parents


def maybe_auto_update(args: argparse.Namespace) -> None:
    """Increment usage counters and run auto-update when policy is due."""
    command = getattr(args, "command", "")
    # ``completion`` prints a shell script to stdout that is typically
    # eval'd or redirected to a file; an auto-update subprocess here would
    # be an unwanted side effect (and could interleave stderr noise), so
    # skip it alongside the explicit update/onboarding flows.
    if command in {"update", "onboarding", "completion"}:
        return

    data = _read_state()
    data["enabled"] = bool(data.get("enabled", True))
    data["command_count"] = int(opt_int(data, "command_count", 0) or 0) + 1
    data["commands_since_check"] = (
        int(opt_int(data, "commands_since_check", 0) or 0) + 1
    )

    if os.environ.get("LOGION_AUTO_UPDATE") == "0":
        return

    if not data["enabled"]:
        _try_write_state(data)
        return

    if _is_npm_managed_python():
        # A skip is not a failure: record it under its own field so JSON
        # consumers can keep treating last_error as "the last real failure".
        data["last_skip_reason"] = (
            "npm-managed install is updated by npm postinstall"
        )
        _try_write_state(data)
        return

    if not _is_due(data):
        _try_write_state(data)
        return

    data["last_attempt_at"] = _now().isoformat()
    if not _try_write_state(data):
        return

    try:
        result = _run_update(args)
    except Exception as exc:
        data = _read_state()
        data["last_checked_at"] = _now().isoformat()
        data["commands_since_check"] = 0
        data["last_error"] = str(exc)
        _try_write_state(data)
        sys.stderr.write("logion: auto-update failed; continuing.\n")
        return

    data = _read_state()
    data["last_checked_at"] = _now().isoformat()
    data["commands_since_check"] = 0
    if result.returncode == 0:
        data["last_success_at"] = data["last_checked_at"]
        data.pop("last_error", None)
        sys.stderr.write("logion: auto-update completed.\n")
    else:
        data["last_error"] = (result.stderr or result.stdout)[-1000:]
        sys.stderr.write("logion: auto-update failed; continuing.\n")
    _try_write_state(data)


def _is_due(data: JsonObject) -> bool:
    commands = int(opt_int(data, "commands_since_check", 0) or 0)
    if commands >= DEFAULT_COMMAND_THRESHOLD:
        return True
    last_checked = _parse_time(data.get("last_checked_at"))
    if last_checked is None:
        return False
    return _now() - last_checked >= timedelta(hours=DEFAULT_INTERVAL_HOURS)


def _run_update(args: argparse.Namespace) -> subprocess.CompletedProcess[str]:
    from cli.commands.update import (
        INSTALLER_URL,
        _download_installer,
        _installer_command,
    )

    update_args = argparse.Namespace(
        channel="latest",
        version=None,
        installer=None,
        dry_run=False,
        timeout=getattr(args, "timeout", None),
    )
    script = _download_installer(INSTALLER_URL, update_args.timeout)
    command = _installer_command(script, update_args)
    try:
        return subprocess.run(
            command,
            check=False,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
        )
    finally:
        with contextlib.suppress(OSError):
            script.unlink()

# SPDX-License-Identifier: MIT
"""Top-level ``logion doctor`` command.

Reports the *authoritative* installed CLI version (from package metadata),
where the running binary lives, how it was installed, and whether the
auxiliary state files under ``~/.logion`` agree with it. The version
reported by ``logion --version`` / this command is always the source of
truth; the ``npm-wrapper-installer.json`` marker and ``auto_update.json``
are operational state that can drift, and this command surfaces that drift
instead of letting it hide.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cli import _auto_update
from cli._local_state import INDEX_FILENAME, get_home, read_index
from cli._options import COMMON_PARSER
from cli._output import emit_json
from cli._version import __version__

# The npm wrapper always installs into ~/.logion regardless of LOGION_HOME,
# so the managed venv and its marker are resolved against the real home, not
# get_home().
NPM_HOME = Path.home() / ".logion"
MANAGED_VENV_DIR = NPM_HOME / _auto_update.NPM_MANAGED_VENV_DIRNAME
MARKER_PATH = NPM_HOME / "npm-wrapper-installer.json"


def _detect_install_method(executable: Path) -> str:
    """Classify how the running CLI was installed from its executable path."""
    resolved = executable.expanduser()
    # The interpreter lives under the venv dir, so parent-membership is the
    # meaningful check (the executable is never equal to the dir itself).
    if MANAGED_VENV_DIR in resolved.parents:
        return "npm-managed-venv"
    parts = [p.lower() for p in resolved.parts]
    if "pipx" in parts:
        return "pipx"
    # uv tools live under .../uv/tools/<name>/...
    if "uv" in parts and "tools" in parts:
        return "uv-tool"
    return "other"


def _read_marker() -> dict[str, Any] | None:
    """Read the npm wrapper install marker, or None if absent/unreadable."""
    try:
        raw = json.loads(MARKER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _collect(home: Path | None = None) -> dict[str, Any]:
    """Gather the diagnostic payload."""
    executable = Path(sys.executable)
    install_method = _detect_install_method(executable)
    marker = _read_marker()
    auto_update = _auto_update.status(home)

    try:
        installed_courses = len(read_index(home))
    except (OSError, json.JSONDecodeError):
        installed_courses = 0

    warnings: list[str] = []

    marker_version = marker.get("version") if marker else None
    if marker_version and marker_version != __version__:
        warnings.append(
            f"{MARKER_PATH.name} records version {marker_version} but the "
            f"running CLI is {__version__}. The npm marker is stale; the "
            f"running version is authoritative."
        )

    if install_method == "npm-managed-venv" and marker is None:
        warnings.append(
            "Running from the npm-managed venv but no "
            f"{MARKER_PATH.name} marker was found; uninstall via npm may "
            "not clean up correctly."
        )

    if auto_update.get("last_error"):
        warnings.append(f"Last auto-update note: {auto_update['last_error']}")

    return {
        "cli_version": __version__,
        "executable": str(executable),
        "install_method": install_method,
        "logion_home": str(get_home()),
        "managed_venv_present": MANAGED_VENV_DIR.is_dir(),
        "npm_marker": marker,
        "auto_update": auto_update,
        "installed_courses": installed_courses,
        "index_file": str((home or get_home()) / INDEX_FILENAME),
        "warnings": warnings,
        "ok": not warnings,
    }


def _print_human(data: dict[str, Any]) -> None:
    out = sys.stdout
    out.write(f"logion CLI {data['cli_version']}\n")
    out.write(f"  install method : {data['install_method']}\n")
    out.write(f"  executable     : {data['executable']}\n")
    out.write(f"  LOGION_HOME     : {data['logion_home']}\n")
    out.write(f"  installed courses: {data['installed_courses']}\n")

    marker = data["npm_marker"]
    if marker:
        out.write(
            "  npm marker     : "
            f"{marker.get('installer', '?')} @ "
            f"{marker.get('version', '?')} "
            f"({marker.get('installedAt', 'unknown time')})\n"
        )
    else:
        out.write("  npm marker     : none\n")

    au = data["auto_update"]
    state = "enabled" if au["enabled"] else "disabled"
    out.write(
        f"  auto-update    : {state}, "
        f"{au['commands_since_check']}/{au['command_threshold']} commands "
        f"since last check\n"
    )

    if data["warnings"]:
        out.write("\nwarnings:\n")
        for warning in data["warnings"]:
            out.write(f"  ! {warning}\n")
    else:
        out.write("\nNo divergence detected.\n")


def handle_doctor(args: argparse.Namespace) -> int:
    """Report version, install location, and state-file consistency."""
    data = _collect()
    if getattr(args, "json_output", False):
        emit_json("logion.doctor", data)
    else:
        _print_human(data)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``doctor`` command."""
    parser = subparsers.add_parser(
        "doctor",
        help=(
            "Report the installed CLI version, where it runs from, and "
            "whether ~/.logion state files agree with it"
        ),
        parents=[COMMON_PARSER],
    )
    parser.set_defaults(handler=handle_doctor)

# SPDX-License-Identifier: MIT
"""Top-level ``logion update`` command."""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from contextlib import suppress
from pathlib import Path

from cli import _auto_update
from cli._options import COMMON_PARSER
from cli._output import emit_json
from cli._version import __version__

INSTALLER_URL = "https://logion.sh/install.sh"
INSTALLER_HEADERS = {
    "Accept": "application/x-sh, text/x-shellscript, text/plain, */*",
    "User-Agent": f"logion-cli/{__version__}",
}


def _installer_command(script: Path, args: argparse.Namespace) -> list[str]:
    """Build the installer command for a parsed ``logion update`` call."""
    command = [
        "sh",
        str(script),
        "--channel",
        args.channel,
        "--no-onboarding",
        "--update",
    ]
    if args.version:
        command.extend(["--version", args.version])
    if args.installer:
        command.extend(["--installer", args.installer])
    if args.dry_run:
        command.append("--dry-run")
    return command


def _download_installer(url: str, timeout: float | None) -> Path:
    """Download the official installer to a temporary executable file."""
    request = urllib.request.Request(url, headers=INSTALLER_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout or 30.0) as response:
        body = response.read()
    with tempfile.NamedTemporaryFile(
        prefix="logion-update-",
        suffix=".sh",
        delete=False,
    ) as handle:
        handle.write(body)
        path = Path(handle.name)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def handle_update(args: argparse.Namespace) -> int:
    """Update Logion CLI and companion through the public installer."""
    auto_update_mode = getattr(args, "auto_update", None)
    if getattr(args, "enable_auto_update", False):
        auto_update_mode = "on"
    if getattr(args, "disable_auto_update", False):
        auto_update_mode = "off"
    if auto_update_mode is not None:
        return _handle_auto_update_mode(auto_update_mode, args)

    try:
        script = _download_installer(INSTALLER_URL, args.timeout)
    except (OSError, urllib.error.URLError) as exc:
        message = f"Failed to download installer: {exc}"
        if getattr(args, "json_output", False):
            emit_json(
                "logion.update",
                {
                    "ok": False,
                    "error": message,
                    "installer_url": INSTALLER_URL,
                },
            )
        else:
            sys.stderr.write(f"ERROR: {message}\n")
        return 5

    command = _installer_command(script, args)
    try:
        if getattr(args, "json_output", False):
            result = subprocess.run(
                command,
                check=False,
                env=os.environ.copy(),
                text=True,
                capture_output=True,
            )
            emit_json(
                "logion.update",
                {
                    "ok": result.returncode == 0,
                    "returncode": result.returncode,
                    "command": command,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            )
            return result.returncode
        return subprocess.run(
            command,
            check=False,
            env=os.environ.copy(),
        ).returncode
    finally:
        with suppress(OSError):
            script.unlink()


def _handle_auto_update_mode(mode: str, args: argparse.Namespace) -> int:
    """Handle auto-update settings without running an installer update."""
    if mode == "on":
        _auto_update.set_enabled(True)
    elif mode == "off":
        _auto_update.set_enabled(False)
    elif mode != "status":
        sys.stderr.write(f"ERROR: unknown auto-update mode: {mode}\n")
        return 2

    data = _auto_update.status()
    if getattr(args, "json_output", False):
        emit_json("logion.update.auto_update", data)
    else:
        status = "enabled" if data["enabled"] else "disabled"
        sys.stderr.write(f"Auto-update is {status}.\n")
        sys.stderr.write(
            "Commands since check: "
            f"{data['commands_since_check']}/{data['command_threshold']}\n"
        )
        if data.get("last_checked_at"):
            sys.stderr.write(f"Last checked: {data['last_checked_at']}\n")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``update`` command."""
    parser = subparsers.add_parser(
        "update",
        help="Update the Logion CLI and companion to the latest release",
        parents=[COMMON_PARSER],
    )
    parser.add_argument(
        "--channel",
        choices=["stable", "latest"],
        default="latest",
        help="Release channel to install (default: latest)",
    )
    parser.add_argument(
        "--version",
        help="Install a specific version instead of the channel latest",
    )
    parser.add_argument(
        "--installer",
        choices=["pipx", "uv", "venv"],
        default=None,
        help="Installer backend to pass through to install.sh",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--auto-update",
        choices=["on", "off", "status"],
        help="Enable, disable, or inspect automatic CLI updates",
    )
    parser.add_argument(
        "--enable-auto-update",
        action="store_true",
        help="Enable automatic CLI updates",
    )
    parser.add_argument(
        "--disable-auto-update",
        action="store_true",
        help="Disable automatic CLI updates",
    )
    parser.set_defaults(handler=handle_update)

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
    parser.set_defaults(handler=handle_update)

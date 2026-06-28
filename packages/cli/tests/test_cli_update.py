# SPDX-License-Identifier: MIT
"""Tests for ``logion update``."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.commands.update import _installer_command


def test_update_installer_command_defaults_to_latest_no_onboarding() -> None:
    """update uses the full installer, including the companion step."""
    args = argparse.Namespace(
        channel="latest",
        version=None,
        installer=None,
        dry_run=False,
    )

    command = _installer_command(Path("/tmp/install.sh"), args)

    assert command == [
        "sh",
        "/tmp/install.sh",
        "--channel",
        "latest",
        "--no-onboarding",
    ]
    assert "--cli-only" not in command
    assert "--skill-only" not in command


def test_update_installer_command_forwards_options() -> None:
    """update forwards version, installer backend, and dry-run."""
    args = argparse.Namespace(
        channel="stable",
        version="0.1.3",
        installer="pipx",
        dry_run=True,
    )

    command = _installer_command(Path("/tmp/install.sh"), args)

    assert command == [
        "sh",
        "/tmp/install.sh",
        "--channel",
        "stable",
        "--no-onboarding",
        "--version",
        "0.1.3",
        "--installer",
        "pipx",
        "--dry-run",
    ]

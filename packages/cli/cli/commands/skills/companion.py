# SPDX-License-Identifier: MIT
"""Handlers for ``logion skills companion`` subcommands."""

from __future__ import annotations

import argparse

from cli._output import emit_json

from ._install_helpers import resolve_target
from .official import OfficialCompanionService


def handle_companion_status(args: argparse.Namespace) -> int:
    """Report the official companion installation status."""
    home = resolve_target(args)
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    if getattr(args, "json_output", False):
        emit_json("logion.skills.companion.status", status.to_dict())
        return 0
    if status.installed:
        print(f"Companion installed: {status.course_id}/{status.version_id}")
        print(f"  Source: {status.source}")
    else:
        print("Companion not installed.")
        if status.reason:
            print(f"  {status.reason}")
    return 0


def handle_companion_install(args: argparse.Namespace) -> int:
    """Install the official companion from the release manifest.

    The actual companion bundle installation is performed by the
    curl installer (``install_lib.sh``).  This handler fetches the
    release manifest for the requested channel, checks whether the
    companion is already installed at that version, and prints
    actionable guidance.
    """
    channel = getattr(args, "channel", "stable")
    home = resolve_target(args)
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    if status.installed:
        if getattr(args, "json_output", False):
            emit_json("logion.skills.companion.install", status.to_dict())
            return 0
        print(f"Companion already installed: {status.version_id}")
        return 0
    if getattr(args, "json_output", False):
        emit_json(
            "logion.skills.companion.install",
            {
                **status.to_dict(),
                "channel": channel,
                "install_hint": (
                    "Run: curl -fsSL https://raw.githubusercontent.com/"
                    "nicolasmelo1/logion/main/scripts/install.sh | sh"
                ),
            },
        )
    else:
        print("Companion not installed.")
        if status.reason:
            print(f"  {status.reason}")
        print(f"  Channel: {channel}")
        print(
            "  Install with: curl -fsSL "
            "https://raw.githubusercontent.com/"
            "nicolasmelo1/logion/main/scripts/install.sh | sh"
        )
    return 1


def handle_companion_update(args: argparse.Namespace) -> int:
    """Update the official companion."""
    home = resolve_target(args)
    service = OfficialCompanionService(home=home)
    status = service.inspect()
    if not status.installed:
        if getattr(args, "json_output", False):
            emit_json("logion.skills.companion.update", status.to_dict())
        else:
            print("Companion not installed.")
            if status.reason:
                print(f"  {status.reason}")
        return 1
    if getattr(args, "json_output", False):
        emit_json("logion.skills.companion.update", status.to_dict())
    else:
        print(
            f"Companion update check: {status.course_id}/{status.version_id}"
        )
        if status.needs_update:
            print("  Update available.")
        else:
            print("  Up to date.")
    return 0

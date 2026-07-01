# SPDX-License-Identifier: MIT
"""Handlers for ``logion skills companion`` subcommands."""

from __future__ import annotations

import argparse

from cli._output import emit_json

from .official import OfficialCompanionService


def handle_companion_status(args: argparse.Namespace) -> int:
    """Report the official companion installation status."""
    service = OfficialCompanionService()
    status = service.inspect()
    if getattr(args, "json_output", False):
        emit_json("logion.skills.companion.status", status.to_dict())
        return 0
    if status.installed:
        pass
    else:
        if status.reason:
            pass
    return 0


def handle_companion_install(args: argparse.Namespace) -> int:
    """Install the official companion from the release manifest."""
    service = OfficialCompanionService()
    status = service.inspect()
    if status.installed:
        if getattr(args, "json_output", False):
            emit_json("logion.skills.companion.install", status.to_dict())
            return 0
        return 0
    if getattr(args, "json_output", False):
        emit_json("logion.skills.companion.install", status.to_dict())
    else:
        pass
    return 0


def handle_companion_update(args: argparse.Namespace) -> int:
    """Update the official companion."""
    service = OfficialCompanionService()
    status = service.inspect()
    if not status.installed:
        if getattr(args, "json_output", False):
            emit_json("logion.skills.companion.update", status.to_dict())
        else:
            pass
        return 1
    if getattr(args, "json_output", False):
        emit_json("logion.skills.companion.update", status.to_dict())
    else:
        pass
    return 0

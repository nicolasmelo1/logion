# SPDX-License-Identifier: MIT
"""Handlers for ``skills installed`` and ``skills updates`` commands."""

from __future__ import annotations

import argparse

from cli._json import JsonObject, opt_str
from cli._local_state import (
    list_installed,
    verify_installed_content,
)
from cli._output import emit_json

from .handlers import resolve_target


def handle_skills_installed(args: argparse.Namespace) -> int:
    """List installed skills."""
    home = resolve_target(args)
    installed = list_installed(home)
    if getattr(args, "json_output", False):
        emit_json("logion.skills.installed", installed)
        return 0
    if not installed:
        print(f"No installed capabilities under {home / 'installed'}.")
        return 0
    print(f"Installed capabilities ({len(installed)}):")
    for m in installed:
        course_id = opt_str(m, "course_id", "?")
        version_id = opt_str(m, "version_id", "?")
        title = opt_str(m, "title", "")
        status = opt_str(m, "review_status", "unknown")
        line = f"  {course_id}/{version_id}"
        if title:
            line += f" — {title}"
        line += f" [{status}]"
        verification = verify_installed_content(course_id, version_id, home)
        if verification["user_modified"]:
            line += " [LOCALLY MODIFIED]"
        print(line)
    return 0


def handle_skills_updates(args: argparse.Namespace) -> int:
    """Report integrity of installed skills."""
    home = resolve_target(args)
    installed = list_installed(home)
    if not installed:
        print(f"No installed capabilities under {home / 'installed'}.")
        return 0
    out: list[JsonObject] = []
    for m in installed:
        course_id = opt_str(m, "course_id", "?")
        version_id = opt_str(m, "version_id", "?")
        verification = verify_installed_content(course_id, version_id, home)
        out.append({
            "course_id": course_id,
            "version_id": version_id,
            "title": opt_str(m, "title", ""),
            "source": opt_str(m, "source", "manual"),
            "entitlement_status": opt_str(m, "entitlement_status", "unknown"),
            "license_scope": opt_str(m, "license_scope", "unknown"),
            "official_update_channel": m.get("official_update_channel", False),
            "last_verified_at": m.get("last_verified_at"),
            "manifest_path": m.get("manifest_path"),
            "entrypoint": opt_str(m, "entrypoint", "SKILL.md"),
            "ok": verification["ok"],
            "user_modified": verification["user_modified"],
        })
    if getattr(args, "json_output", False):
        emit_json("logion.skills.updates", out)
        return 0
    print(f"Update status ({len(out)} installed):")
    for entry in out:
        flags: list[str] = []
        if entry["user_modified"]:
            flags.append("locally-modified")
        if not entry["ok"] and not entry["user_modified"]:
            flags.append("integrity-unknown")
        suffix = f" [{', '.join(flags)}]" if flags else ""
        print(f"  {entry['course_id']}/{entry['version_id']}{suffix}")
    return 0

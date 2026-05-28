"""Handlers for the ``skills`` command group.

These commands operate entirely on the local ``~/.logion/`` cache; they
do not call the marketplace API.  The companion package (and any
agent) talks to the local cache through this CLI surface so install,
update, and inspection paths run through the same validators as the
rest of the CLI.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from cli._local_state import (
    LockHeldError,
    UnsafeIdentifierError,
    _utc_iso_now,
    acquire_lock,
    installed_dir,
    list_installed,
    validate_manifest,
    verify_installed_content,
)
from cli._output import emit_json

from ._finalize import copy_and_finalize
from ._inspect_handler import handle_skills_inspect  # noqa: F401  (re-export)
from ._install_helpers import (
    check_existing_install,
    copy_skill_files,
    read_capabilities,
    resolve_target,
)
from ._update_handler import handle_skills_update  # noqa: F401  (re-export)
from ._verify_handler import handle_skills_verify  # noqa: F401  (re-export)


def handle_skills_install(args: argparse.Namespace) -> int:
    """Install a skill bundle from a local source directory."""
    home = resolve_target(args)
    source_dir = args.source.resolve()
    course_id: str = args.course_id
    version_id: str = args.version_id

    if not (source_dir / "SKILL.md").is_file():
        print(
            f"ERROR: source directory must contain SKILL.md: {source_dir}",
            file=sys.stderr,
        )
        return 1

    if not args.force:
        try:
            rc = check_existing_install(
                course_id, version_id, source_dir, home
            )
        except UnsafeIdentifierError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if rc != 0:
            return rc

    install_source = getattr(args, "install_source", "logion")
    is_marketplace = install_source == "logion-marketplace"
    manifest_data: dict[str, Any] = {
        "course_id": course_id,
        "version_id": version_id,
        "title": args.title or "",
        "source": install_source,
        "installed_at": "",
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal", "file"],
        "permissions": [],
        "env_vars": [],
        "execution_policy": "approval-required",
        "content_sha256": "",
        "review_status": "approved",
        "entitlement_status": "active" if is_marketplace else "unknown",
        "license_scope": "unknown",
        "official_update_channel": is_marketplace,
        "last_verified_at": _utc_iso_now() if is_marketplace else None,
    }
    manifest_data = read_capabilities(
        source_dir / "course" / "capabilities.yaml", manifest_data
    )

    # Validate the manifest *before* touching the filesystem so an
    # invalid bundle (including dry-run) cannot leave a partial copy
    # behind or report success without a real install.
    pre_errors = validate_manifest({**manifest_data, "content_sha256": "_"})
    if pre_errors:
        for e in pre_errors:
            print(f"MANIFEST ERROR: {e}", file=sys.stderr)
        return 3

    try:
        dest = installed_dir(course_id, version_id, home)
    except UnsafeIdentifierError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        copied = copy_skill_files(source_dir, dest, dry_run=True)
        print(
            f"Would install: {course_id}/{version_id} "
            f"({len(copied)} files) -> {dest}"
        )
        return 0

    try:
        acquire_lock(course_id, version_id, home)
    except LockHeldError as exc:
        print(
            f"ERROR: another install/update holds the lock for "
            f"{course_id}/{version_id} at {exc.path}. Wait for it to "
            "finish or remove the stale lock file.",
            file=sys.stderr,
        )
        return 4

    rc, copied = copy_and_finalize(
        source_dir, dest, course_id, version_id, manifest_data, home
    )
    if rc != 0:
        return rc

    print(
        f"Installed: {course_id}/{version_id} ({len(copied)} files) -> {dest}"
    )
    return 0


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
        course_id = m.get("course_id", "?")
        version_id = m.get("version_id", "?")
        title = m.get("title", "")
        status = m.get("review_status", "unknown")
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
    """Report integrity of installed skills (local-only update status)."""
    home = resolve_target(args)
    installed = list_installed(home)
    if not installed:
        print(f"No installed capabilities under {home / 'installed'}.")
        return 0
    out: list[dict[str, Any]] = []
    for m in installed:
        course_id = m.get("course_id", "?")
        version_id = m.get("version_id", "?")
        verification = verify_installed_content(course_id, version_id, home)
        out.append({
            "course_id": course_id,
            "version_id": version_id,
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

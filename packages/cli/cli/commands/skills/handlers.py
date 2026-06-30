# SPDX-License-Identifier: MIT
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
from pathlib import Path
from typing import Any

from cli._course_bundle import CourseBundleError, validate_course_bundle
from cli._local_state import (
    LockHeldError,
    UnsafeIdentifierError,
    _utc_iso_now,
    acquire_lock,
    enrich_manifest,
    installed_dir,
    validate_manifest,
)
from cli._output import emit_json

from ._agent_symlink import (
    apply_post_install_symlink,
    resolve_symlink_intent,
)
from ._finalize import copy_and_finalize
from ._inspect_handler import handle_skills_inspect  # noqa: F401  (re-export)
from ._install_helpers import (
    check_existing_install,
    copy_skill_files,
    read_capabilities,
    resolve_target,
)
from ._query_handlers import (  # noqa: F401  (re-export)
    handle_skills_installed,
    handle_skills_updates,
)
from ._update_handler import handle_skills_update  # noqa: F401  (re-export)
from ._verify_handler import handle_skills_verify  # noqa: F401  (re-export)


def _build_manifest_data(
    args: argparse.Namespace,
    course_id: str,
    version_id: str,
    source_dir: Path,
) -> dict[str, Any]:
    """Build the manifest dict for an install."""
    install_source = getattr(args, "install_source", "manual")
    is_marketplace = install_source == "logion-marketplace"
    data: dict[str, Any] = {
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
    return read_capabilities(source_dir / "course" / "capabilities.yaml", data)


def _validate_pre_install(
    manifest_data: dict[str, Any],
    course_id: str,
    version_id: str,
    home: Path,
) -> int:
    """Validate manifest before filesystem writes. Returns 0 on success."""
    pre_manifest = enrich_manifest(
        {
            **manifest_data,
            "installed_at": (
                manifest_data.get("installed_at") or _utc_iso_now()
            ),
            "content_sha256": "_",
        },
        course_id,
        version_id,
        home,
    )
    pre_errors = validate_manifest(pre_manifest)
    if pre_errors:
        for e in pre_errors:
            print(f"MANIFEST ERROR: {e}", file=sys.stderr)
        return 3
    return 0


def handle_skills_install(args: argparse.Namespace) -> int:  # noqa: C901
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
    try:
        validate_course_bundle(source_dir)
    except CourseBundleError as exc:
        print(f"ERROR: invalid course bundle: {exc}", file=sys.stderr)
        return 1

    # Ask about the agent skill copy up-front, before any filesystem writes.
    # The user's choice is captured here and applied after install.
    skill_name, symlink_parent = resolve_symlink_intent(source_dir, args)

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

    manifest_data = _build_manifest_data(
        args, course_id, version_id, source_dir
    )

    # Validate the manifest *before* touching the filesystem so an
    # invalid bundle (including dry-run) cannot leave a partial copy
    # behind or report success without a real install.
    rc = _validate_pre_install(manifest_data, course_id, version_id, home)
    if rc != 0:
        return rc

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

    if symlink_parent and skill_name:
        apply_post_install_symlink(symlink_parent, skill_name, dest)

    if getattr(args, "json_output", False):
        emit_json(
            "logion.skills.install",
            {
                "course_id": course_id,
                "version_id": version_id,
                "destination": str(dest),
                "files_installed": len(copied),
                "agent_skill_copied": bool(symlink_parent and skill_name),
                # Kept for backwards compatibility with older JSON consumers.
                "symlinked": bool(symlink_parent and skill_name),
            },
        )
    return 0

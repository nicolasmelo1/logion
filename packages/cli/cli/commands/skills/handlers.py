"""Handlers for the ``skills`` command group.

These commands operate entirely on the local ``~/.logion/`` cache; they
do not call the marketplace API.  The companion package (and any
agent) talks to the local cache through this CLI surface so install,
update, and inspection paths run through the same validators as the
rest of the CLI.
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from typing import Any

from cli._local_state import (
    acquire_lock,
    build_index,
    list_installed,
    read_manifest,
    rebuild_recall,
    release_lock,
    validate_manifest,
    verify_installed_content,
    write_index,
    write_manifest,
)

from ._install_helpers import (
    check_existing_install,
    compute_content_hash,
    copy_skill_files,
    read_capabilities,
    resolve_target,
)


def handle_skills_install(args: argparse.Namespace) -> int:
    """Install a skill bundle from a local source directory."""
    home = resolve_target(args)
    source = args.source.resolve()
    course_id: str = args.course_id
    version_id: str = args.version_id

    if not (source / "SKILL.md").is_file():
        print(
            f"ERROR: source directory must contain SKILL.md: {source}",
            file=sys.stderr,
        )
        return 1

    if not args.force:
        rc = check_existing_install(course_id, version_id, source, home)
        if rc != 0:
            return rc

    manifest_data: dict[str, Any] = {
        "course_id": course_id,
        "version_id": version_id,
        "title": args.title or "",
        "source": "logion",
        "installed_at": "",
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal", "file"],
        "content_sha256": "",
        "review_status": "approved",
    }
    manifest_data = read_capabilities(
        source / "course" / "capabilities.yaml", manifest_data
    )

    dest = home / "installed" / course_id / version_id

    if args.dry_run:
        copied = copy_skill_files(source, dest, dry_run=True)
        print(
            f"Would install: {course_id}/{version_id} "
            f"({len(copied)} files) -> {dest}"
        )
        return 0

    acquire_lock(course_id, version_id, home)
    try:
        if dest.exists():
            shutil.rmtree(dest)
        copied = copy_skill_files(source, dest, dry_run=False)
        existing_files = [p for p in sorted(dest.rglob("*")) if p.is_file()]
        manifest_data["content_sha256"] = compute_content_hash(existing_files)
        manifest_data["installed_at"] = datetime.datetime.now(
            datetime.UTC
        ).isoformat()
        errors = validate_manifest(manifest_data)
        if errors:
            for e in errors:
                print(f"MANIFEST ERROR: {e}", file=sys.stderr)
            return 3
        write_manifest(manifest_data, course_id, version_id, home)
    finally:
        release_lock(course_id, version_id, home)

    write_index(build_index(home), home)
    rebuild_recall(home)
    print(
        f"Installed: {course_id}/{version_id} ({len(copied)} files) -> {dest}"
    )
    return 0


def handle_skills_installed(args: argparse.Namespace) -> int:
    """List installed skills."""
    home = resolve_target(args)
    installed = list_installed(home)
    if getattr(args, "json_output", False):
        print(json.dumps(installed, indent=2, sort_keys=True))
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


def handle_skills_inspect(args: argparse.Namespace) -> int:
    """Show the manifest for an installed skill."""
    home = resolve_target(args)
    course_id: str = args.course_id
    version_id: str | None = getattr(args, "version_id", None)
    if version_id is None:
        candidates = [
            m for m in list_installed(home) if m.get("course_id") == course_id
        ]
        if not candidates:
            print(
                f"No installation found for course {course_id}",
                file=sys.stderr,
            )
            return 1
        manifest = candidates[-1]
    else:
        manifest = read_manifest(course_id, version_id, home) or {}
        if not manifest:
            print(
                f"No installation found for {course_id}/{version_id}",
                file=sys.stderr,
            )
            return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
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
        print(json.dumps(out, indent=2, sort_keys=True))
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


def handle_skills_update(args: argparse.Namespace) -> int:
    """Apply an update with safety policy.

    Refuses to overwrite a locally modified installation unless
    ``--force`` is passed.  Delegates the copy to the install handler
    with ``--force`` set.
    """
    home = resolve_target(args)
    course_id: str = args.course_id
    version_id: str = args.version_id
    verification = verify_installed_content(course_id, version_id, home)
    if verification["user_modified"] and not args.force:
        print(
            f"Refusing to update {course_id}/{version_id}: local "
            "modifications detected. Pass --force to overwrite.",
            file=sys.stderr,
        )
        return 2
    install_args = argparse.Namespace(
        source=args.source,
        course_id=course_id,
        version_id=version_id,
        title=getattr(args, "title", None),
        target=getattr(args, "target", None),
        dry_run=False,
        force=True,
    )
    return handle_skills_install(install_args)

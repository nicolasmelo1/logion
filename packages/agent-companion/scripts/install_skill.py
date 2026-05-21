#!/usr/bin/env python3
"""Install a Logion capability from a packaged source directory.

Usage:
    python scripts/install_skill.py SOURCE_DIR [OPTIONS]

Options:
    --dry-run       Show what would be done without writing files
    --target PATH   Override LOGION_HOME (default: ~/.logion)
    --help          Show this help message
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import shutil
import sys
from pathlib import Path

import yaml

from logion_agent_companion.local_state import (
    acquire_lock,
    build_index,
    build_recall_entries,
    ensure_layout,
    list_installed,
    read_manifest,
    read_workflows,
    release_lock,
    validate_manifest,
    write_index,
    write_manifest,
    write_recall,
)


def _collect_source_files(source_dir: Path) -> list[Path]:
    """Return sorted source files (excluding manifest.json)."""
    return sorted(
        p
        for p in source_dir.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    )


def _compute_content_hash(files: list[Path]) -> str:
    """Return SHA-256 of concatenated file contents."""
    if not files:
        return ""
    return hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()


def _read_capabilities(
    cap_yaml: Path,
    manifest_data: dict,
) -> dict:
    """Update *manifest_data* with capabilities.yaml data if present."""
    if not cap_yaml.is_file():
        return manifest_data
    try:
        cap_data = yaml.safe_load(cap_yaml.read_text(encoding="utf-8"))
        if isinstance(cap_data, dict):
            manifest_data["capabilities"] = [
                c.get("id", "")
                for c in cap_data.get("capabilities", [])
                if isinstance(c, dict) and "id" in c
            ]
            manifest_data["required_tools"] = cap_data.get(
                "required_tools", ["terminal", "file"]
            )
    except yaml.YAMLError:
        pass
    return manifest_data


def _check_existing_install(
    course_id: str,
    version_id: str,
    source_dir: Path,
    home: Path,
) -> int:
    """Return 0 if install can proceed, 2 if conflicting install exists."""
    existing = read_manifest(course_id, version_id, home)
    if existing is None:
        return 0
    existing_hash = existing.get("content_sha256", "")
    source_files = _collect_source_files(source_dir)
    new_hash = _compute_content_hash(source_files)
    if existing_hash and new_hash != existing_hash:
        print(
            f"ERROR: {course_id}/{version_id} already installed with "
            "different content. Use --force to overwrite or update "
            "explicitly.",
            file=sys.stderr,
        )
        return 2
    return 0


def _copy_skill_files(
    src: Path,
    dest: Path,
    dry_run: bool = False,
) -> list[Path]:
    """Copy SKILL.md and supporting dirs from *src* to *dest*."""
    copied: list[Path] = []
    for name in ("SKILL.md",):
        s = src / name
        if not s.is_file():
            print(
                f"WARNING: {s} not found, skipping",
                file=sys.stderr,
            )
            continue
        d = dest / name
        if not dry_run:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
        copied.append(d)

    for subdir in ("course", "references", "templates"):
        sdir = src / subdir
        if sdir.is_dir():
            for child in sorted(sdir.rglob("*")):
                if child.is_file():
                    rel = child.relative_to(src)
                    d = dest / rel
                    if not dry_run:
                        d.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(child, d)
                    copied.append(d)

    return copied


def install_skill(
    source_dir: Path,
    course_id: str,
    version_id: str,
    *,
    target: Path | None = None,
    dry_run: bool = False,
) -> int:
    """Install a skill package from *source_dir* into the local cache.

    Returns 0 on success, non-zero on failure.
    """
    home = target or ensure_layout()
    dest = home / "installed" / course_id / version_id

    skill_md = source_dir / "SKILL.md"
    if not skill_md.is_file():
        print(
            f"ERROR: source directory must contain SKILL.md: {source_dir}",
            file=sys.stderr,
        )
        return 1

    rc = _check_existing_install(course_id, version_id, source_dir, home)
    if rc != 0:
        return rc

    cap_yaml = source_dir / "course" / "capabilities.yaml"
    manifest_data: dict = {
        "course_id": course_id,
        "version_id": version_id,
        "title": "",
        "source": "logion",
        "installed_at": "",
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal", "file"],
        "content_sha256": "",
        "review_status": "approved",
    }
    manifest_data = _read_capabilities(cap_yaml, manifest_data)

    if not dry_run:
        acquire_lock(course_id, version_id, home)

    try:
        if dest.exists() and not dry_run:
            shutil.rmtree(dest)
        copied = _copy_skill_files(source_dir, dest, dry_run)

        if not dry_run:
            existing_files = [
                p for p in sorted(dest.rglob("*")) if p.is_file()
            ]
            manifest_data["content_sha256"] = _compute_content_hash(
                existing_files
            )
            manifest_data["installed_at"] = datetime.datetime.now(
                datetime.UTC
            ).isoformat()

        errors = validate_manifest(manifest_data)
        if errors:
            for e in errors:
                print(f"MANIFEST ERROR: {e}", file=sys.stderr)
            if not dry_run:
                return 3

        if not dry_run:
            write_manifest(manifest_data, course_id, version_id, home)

    finally:
        if not dry_run:
            release_lock(home)

    if not dry_run:
        installed = list_installed(home)
        write_index(build_index(home), home)
        write_recall(
            build_recall_entries(installed, read_workflows(home)),
            home,
        )

    action = "Would install" if dry_run else "Installed"
    print(
        f"{action}: {course_id}/{version_id} ({len(copied)} files) -> {dest}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install a Logion capability from a source directory.",
    )
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Path to the skill package source directory.",
    )
    parser.add_argument(
        "--course-id",
        required=True,
        help="Course identifier (e.g. weather.basic).",
    )
    parser.add_argument(
        "--version-id",
        required=True,
        help="Version identifier (e.g. 2026.05.20).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing files.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Override LOGION_HOME for the install target.",
    )
    args = parser.parse_args()

    return install_skill(
        source_dir=args.source_dir.resolve(),
        course_id=args.course_id,
        version_id=args.version_id,
        target=args.target,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())

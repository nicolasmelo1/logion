"""Internal helpers shared by the ``skills install`` and ``update``
handlers.  Kept separate so handlers.py stays under the CLI's per-file
source-size budget."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from cli._local_state import (
    build_index,
    ensure_layout,
    read_manifest,
    rebuild_recall,
    release_lock,
    validate_manifest,
    write_index,
    write_manifest,
)

# Subset of ``source_dir`` that ``copy_skill_files`` actually installs.
# Hashing must scan the same subset, otherwise extra files in the
# source bundle (scripts/, tests/, etc.) produce false "different
# content" errors against a manifest hash computed over only the
# installed files.
INSTALLED_SUBDIRS: tuple[str, ...] = ("course", "references", "templates")


def resolve_target(args: argparse.Namespace) -> Path:
    """Resolve LOGION_HOME from ``--target`` or the environment."""
    target: Path | None = getattr(args, "target", None)
    return ensure_layout(target)


def collect_installable_files(source_dir: Path) -> list[Path]:
    """Return the files that ``copy_skill_files`` would install.

    Same algorithm as :func:`copy_skill_files` so a pre-copy hash can
    be compared apples-to-apples against the post-install manifest
    hash.  Excludes anything outside ``SKILL.md`` and
    :data:`INSTALLED_SUBDIRS`.
    """
    out: list[Path] = []
    skill_md = source_dir / "SKILL.md"
    if skill_md.is_file():
        out.append(skill_md)
    for subdir in INSTALLED_SUBDIRS:
        sdir = source_dir / subdir
        if not sdir.is_dir():
            continue
        for child in sdir.rglob("*"):
            if child.is_file() and child.name != "manifest.json":
                out.append(child)
    return sorted(out)


def compute_content_hash(files: list[Path], root: Path | None = None) -> str:
    """Return SHA-256 over *files*, prefixing each with its rel path + length.

    Streams each file through ``hash.update`` (no ``b"".join``) so
    large skills do not balloon memory.  When *root* is provided,
    paths are taken relative to it; otherwise the file name is used.
    """
    if not files:
        return ""
    h = hashlib.sha256()
    for p in sorted(files):
        if root is not None:
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                rel = p.name
        else:
            rel = p.name
        data = p.read_bytes()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(len(data)).encode("ascii"))
        h.update(b"\0")
        h.update(data)
        h.update(b"\0")
    return h.hexdigest()


def read_capabilities(
    cap_yaml: Path,
    manifest_data: dict[str, Any],
) -> dict[str, Any]:
    """Update *manifest_data* with capabilities.yaml data if present."""
    if not cap_yaml.is_file():
        return manifest_data
    try:
        cap_data = yaml.safe_load(cap_yaml.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return manifest_data
    if not isinstance(cap_data, dict):
        return manifest_data
    manifest_data["capabilities"] = [
        c.get("id", "")
        for c in cap_data.get("capabilities", [])
        if isinstance(c, dict) and "id" in c
    ]
    manifest_data["required_tools"] = cap_data.get(
        "tools", manifest_data.get("required_tools", ["terminal", "file"])
    )
    return manifest_data


def check_existing_install(
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
    new_hash = compute_content_hash(
        collect_installable_files(source_dir), root=source_dir
    )
    if existing_hash and new_hash != existing_hash:
        print(
            f"ERROR: {course_id}/{version_id} already installed with "
            "different content. Re-run `logion skills install ... --force` "
            "to overwrite, or use `logion skills update` for the safety "
            "checks.",
            file=sys.stderr,
        )
        return 2
    return 0


def copy_skill_files(
    src: Path,
    dest: Path,
    dry_run: bool,
) -> list[Path]:
    """Copy SKILL.md and supporting dirs from *src* to *dest*."""
    copied: list[Path] = []
    skill_md = src / "SKILL.md"
    if skill_md.is_file():
        target = dest / "SKILL.md"
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(skill_md, target)
        copied.append(target)
    for subdir in INSTALLED_SUBDIRS:
        sdir = src / subdir
        if not sdir.is_dir():
            continue
        for child in sorted(sdir.rglob("*")):
            if not child.is_file():
                continue
            target = dest / child.relative_to(src)
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)
            copied.append(target)
    return copied


def copy_and_finalize(
    source: Path,
    dest: Path,
    course_id: str,
    version_id: str,
    manifest_data: dict[str, Any],
    home: Path,
) -> tuple[int, list[Path]]:
    """Copy files, write manifest+index+recall, and release the lock.

    Split out of :func:`handle_skills_install` so the handler stays
    under the project's complexity budget.  Returns
    ``(exit_code, copied)``; on failure the partial install is removed
    so the next attempt is not confused by orphan files.
    """
    try:
        if dest.exists():
            shutil.rmtree(dest)
        copied = copy_skill_files(source, dest, dry_run=False)
        existing_files = [p for p in sorted(dest.rglob("*")) if p.is_file()]
        manifest_data["content_sha256"] = compute_content_hash(
            existing_files, root=dest
        )
        manifest_data["installed_at"] = datetime.datetime.now(
            datetime.UTC
        ).isoformat()
        errors = validate_manifest(manifest_data)
        if errors:
            for e in errors:
                print(f"MANIFEST ERROR: {e}", file=sys.stderr)
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            return 3, copied
        write_manifest(manifest_data, course_id, version_id, home)
    finally:
        release_lock(course_id, version_id, home)

    write_index(build_index(home), home)
    rebuild_recall(home)
    return 0, copied

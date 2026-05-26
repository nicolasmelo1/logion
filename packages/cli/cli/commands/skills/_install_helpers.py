"""Internal helpers shared by the ``skills install`` and ``update``
handlers.  Kept separate so handlers.py stays under the CLI's per-file
source-size budget."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from cli._local_state import ensure_layout, read_manifest

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


_HASH_CHUNK = 64 * 1024  # 64 KiB — keeps peak memory bounded for big files.


def compute_content_hash(files: list[Path], root: Path | None = None) -> str:
    """Return SHA-256 over *files*, prefixing each with its rel path + length.

    Reads each file in :data:`_HASH_CHUNK`-sized chunks so the peak
    memory cost is bounded regardless of file size.  Each file
    contributes ``<rel_path>\\0<length>\\0<bytes>\\0`` so renames or
    repartitioning change the digest.  When *root* is provided, paths
    are taken relative to it; otherwise the file name is used.
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
        size = p.stat().st_size
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(size).encode("ascii"))
        h.update(b"\0")
        with p.open("rb") as fh:
            while True:
                chunk = fh.read(_HASH_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
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
    """Copy SKILL.md and supporting dirs from *src* to *dest*.

    Excludes any ``manifest.json`` under the source tree — the manifest
    is the install's own metadata, not part of the skill content, and
    excluding it here keeps ``copy_skill_files`` byte-for-byte aligned
    with the file set :func:`collect_installable_files` enumerates.
    """
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
            if not child.is_file() or child.name == "manifest.json":
                continue
            target = dest / child.relative_to(src)
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)
            copied.append(target)
    return copied

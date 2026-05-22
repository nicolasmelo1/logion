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


def resolve_target(args: argparse.Namespace) -> Path:
    """Resolve LOGION_HOME from ``--target`` or the environment."""
    target: Path | None = getattr(args, "target", None)
    return ensure_layout(target)


def collect_source_files(source_dir: Path) -> list[Path]:
    """Return sorted source files (excluding manifest.json)."""
    return sorted(
        p
        for p in source_dir.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    )


def compute_content_hash(files: list[Path]) -> str:
    """Return SHA-256 of concatenated file contents."""
    if not files:
        return ""
    return hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()


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
    new_hash = compute_content_hash(collect_source_files(source_dir))
    if existing_hash and new_hash != existing_hash:
        print(
            f"ERROR: {course_id}/{version_id} already installed with "
            "different content. Re-run with --force to overwrite.",
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
    for subdir in ("course", "references", "templates"):
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

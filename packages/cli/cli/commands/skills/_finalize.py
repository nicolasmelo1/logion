# SPDX-License-Identifier: MIT
"""Finalisation step for ``logion skills install``.

Kept separate from :mod:`_install_helpers` so each source file stays
under the per-file line budget enforced by ``test_cli_architecture``.
"""

from __future__ import annotations

import datetime
import shutil
import sys
from pathlib import Path
from typing import Any

from cli._local_state import (
    build_index,
    enrich_manifest,
    rebuild_recall,
    release_lock,
    state_lock,
    validate_manifest,
    write_index,
    write_manifest,
)

from ._install_helpers import compute_content_hash, copy_skill_files


def copy_and_finalize(
    source: Path,
    dest: Path,
    course_id: str,
    version_id: str,
    manifest_data: dict[str, Any],
    home: Path,
) -> tuple[int, list[Path]]:
    """Copy files, write manifest+index+recall, and release the lock.

    Returns ``(exit_code, copied)``.  On failure the partial install
    is removed so the next attempt is not confused by orphan files.
    Filesystem errors (rmtree/copy2/hashing) are caught and reported
    as exit code 5 rather than allowed to crash the CLI.
    """
    copied: list[Path] = []
    try:
        try:
            if dest.exists():
                shutil.rmtree(dest)
            copied = copy_skill_files(source, dest, dry_run=False)
            existing_files = [
                p for p in sorted(dest.rglob("*")) if p.is_file()
            ]
            manifest_data["content_sha256"] = compute_content_hash(
                existing_files, root=dest
            )
        except (OSError, shutil.Error) as exc:
            print(
                f"ERROR: filesystem error while installing "
                f"{course_id}/{version_id}: {exc}",
                file=sys.stderr,
            )
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            return 5, copied

        manifest_data["installed_at"] = datetime.datetime.now(
            datetime.UTC
        ).isoformat()
        manifest_data = enrich_manifest(
            manifest_data,
            course_id,
            version_id,
            home,
        )
        errors = validate_manifest(manifest_data)
        if errors:
            for e in errors:
                print(f"MANIFEST ERROR: {e}", file=sys.stderr)
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            return 3, copied
        try:
            write_manifest(manifest_data, course_id, version_id, home)
        except OSError as exc:
            print(
                f"ERROR: failed to write manifest for "
                f"{course_id}/{version_id}: {exc}",
                file=sys.stderr,
            )
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            return 5, copied
    finally:
        release_lock(course_id, version_id, home)

    try:
        # state_lock serializes the index+recall refresh so a parallel
        # install or `recall record` cannot race and drop entries.
        with state_lock(home):
            write_index(build_index(home), home)
            rebuild_recall(home)
    except OSError as exc:
        # Install succeeded on disk; only the index/recall refresh
        # failed.  Report but do not roll back — the next install or
        # recall rebuild will repair the indexes.
        print(
            f"WARNING: install succeeded but index/recall refresh "
            f"failed: {exc}",
            file=sys.stderr,
        )
    return 0, copied

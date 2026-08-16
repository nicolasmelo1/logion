# SPDX-License-Identifier: MIT
"""Persistent record of agent-harness skill copies.

``logion skills install --symlink-dir`` (and identity onboarding) copy
an installed skill into an agent harness directory such as
``~/.claude/skills``.  The canonical install lives under
``$LOGION_HOME/installed/<course>/<version>/``; the harness copy is a
projection of that state.  Without a record of where the projections
went, ``logion skills update`` refreshes the canonical install but
leaves every harness copy at the old version.

This module keeps one entry per ``(course_id, target_dir)`` in
``$LOGION_HOME/agent_copies.json`` and re-projects recorded copies
after a successful install or update.  A copy the user has deleted
from the harness dir is treated as an opt-out: its record is dropped,
never resurrected.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from cli._json import JsonObject
from cli._local_state import (
    _read_json_entries,
    _utc_iso_now,
    _write_json_entries,
)

from ._agent_symlink import create_symlink

AGENT_COPIES_FILE = "agent_copies.json"


def _copies_path(home: Path) -> Path:
    return home / AGENT_COPIES_FILE


def read_agent_copies(home: Path) -> list[JsonObject]:
    """Return all recorded harness copies (empty on missing/bad file)."""
    return _read_json_entries(_copies_path(home))


def record_agent_copy(
    home: Path,
    *,
    course_id: str,
    skill_name: str,
    target_dir: Path,
    version_id: str,
) -> None:
    """Upsert the record for a harness copy of *course_id*.

    Keyed by ``(course_id, target_dir)`` so re-installing into the same
    harness dir updates the existing entry instead of duplicating it.
    """
    target = str(Path(target_dir).expanduser().resolve())
    entries = read_agent_copies(home)
    entries = [
        e
        for e in entries
        if not (
            e.get("course_id") == course_id and e.get("target_dir") == target
        )
    ]
    entries.append({
        "course_id": course_id,
        "skill_name": skill_name,
        "target_dir": target,
        "version_id": version_id,
        "synced_at": _utc_iso_now(),
    })
    _write_json_entries(_copies_path(home), entries)


def _remove_stale_copy(target: Path) -> None:
    """Remove a previous copy at *target* (name-change cleanup)."""
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)


def sync_agent_copies(
    home: Path,
    *,
    course_id: str,
    version_id: str,
    install_dest: Path,
    skill_name: str | None,
) -> list[str]:
    """Re-copy every recorded harness copy of *course_id*.

    Returns the refreshed target paths.  Records whose copy no longer
    exists on disk are dropped (the user removed it — do not
    resurrect).  A failed re-copy keeps its record and warns, so the
    next update retries.
    """
    entries = read_agent_copies(home)
    kept: list[JsonObject] = []
    synced: list[str] = []
    changed = False
    for entry in entries:
        if entry.get("course_id") != course_id:
            kept.append(entry)
            continue
        parent = Path(str(entry.get("target_dir") or ""))
        old_name = str(entry.get("skill_name") or "")
        if not parent.name or not old_name:
            changed = True  # unusable record; drop it
            continue
        old_target = parent / old_name
        if not old_target.exists():
            sys.stderr.write(
                f"NOTICE: harness copy {old_target} was removed; "
                "dropping its sync record\n"
            )
            changed = True
            continue
        new_name = skill_name or old_name
        try:
            if new_name != old_name:
                _remove_stale_copy(old_target)
            target = create_symlink(parent, new_name, install_dest)
        except OSError as exc:
            sys.stderr.write(
                f"WARN: refresh of harness copy {old_target} failed "
                f"({exc}); canonical install is fine\n"
            )
            kept.append(entry)
            continue
        kept.append({
            **entry,
            "skill_name": new_name,
            "version_id": version_id,
            "synced_at": _utc_iso_now(),
        })
        synced.append(str(target))
        changed = True
    if changed:
        _write_json_entries(_copies_path(home), kept)
    return synced

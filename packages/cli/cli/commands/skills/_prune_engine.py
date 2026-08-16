# SPDX-License-Identifier: MIT
"""Retention engine and data classes for ``logion skills prune``.

Kept separate from :mod:`prune` so the handler module stays under the
CLI's per-file source-size budget.
"""

from __future__ import annotations

import contextlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cli._json import JsonObject, opt_str
from cli._local_state import (
    _safe_segment,
    build_index,
    build_recall_entries,
    list_installed,
    read_index,
    read_workflows,
    verify_installed_content,
    write_index,
    write_recall,
)

DEFAULT_KEEP = 3


@dataclass(frozen=True)
class InstalledVersionRef:
    """A single installed version reference for retention planning."""

    course_id: str
    version_id: str
    version: str | None
    installed_at: datetime
    protected: bool
    path: Path


@dataclass(frozen=True)
class RetentionPlan:
    """The result of retention planning for one course."""

    course_id: str
    keep: tuple[InstalledVersionRef, ...]
    remove: tuple[InstalledVersionRef, ...]
    reason: str


def _parse_iso(value: str | None) -> datetime:
    """Parse an ISO 8601 string; fall back to epoch for bad data."""
    if not value:
        return datetime.fromtimestamp(0, tz=UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.fromtimestamp(0, tz=UTC)


def _workflow_version_ids(
    workflows: list[JsonObject],
    course_id: str,
) -> frozenset[str]:
    """Return version_ids referenced by workflows for *course_id*."""
    ids: set[str] = set()
    for w in workflows:
        cid = w.get("course_id")
        vid = w.get("version_id")
        if cid == course_id and isinstance(vid, str) and vid:
            ids.add(vid)
    return frozenset(ids)


def _active_version_id(
    index: list[JsonObject],
    course_id: str,
) -> str | None:
    """Return the active version_id for *course_id* from index.json."""
    for entry in index:
        if entry.get("course_id") == course_id:
            vid = entry.get("version_id")
            if isinstance(vid, str) and vid:
                return vid
    return None


class LocalState:
    """Thin adapter giving :class:`InstalledVersionRetention` a home."""

    def __init__(self, home: Path) -> None:
        self.home = home


class InstalledVersionRetention:
    """Plan and apply bounded retention on installed versions."""

    def __init__(self, state: LocalState) -> None:
        """Initialize with a state holder carrying ``home``."""
        self._state = state

    def plan(
        self,
        course_id: str,
        keep: int = DEFAULT_KEEP,
        *,
        force_modified: bool = False,
    ) -> RetentionPlan:
        """Build a :class:`RetentionPlan` for *course_id*."""
        home: Path = self._state.home
        _safe_segment(course_id, "course_id")

        installed = list_installed(home)
        course_versions = [
            m for m in installed if m.get("course_id") == course_id
        ]
        if not course_versions:
            return RetentionPlan(
                course_id=course_id,
                keep=(),
                remove=(),
                reason="no installed versions for course",
            )

        index = read_index(home)
        active_vid = _active_version_id(index, course_id)

        workflows = read_workflows(home)
        workflow_vids = _workflow_version_ids(workflows, course_id)

        refs: list[InstalledVersionRef] = []
        for m in course_versions:
            vid = str(opt_str(m, "version_id", ""))
            installed_at = _parse_iso(m.get("installed_at"))
            version_label = m.get("version")
            if not isinstance(version_label, str):
                version_label = None
            version_dir = home / "installed" / course_id / vid
            protected = False
            if vid == active_vid or vid in workflow_vids:
                protected = True
            else:
                verification = verify_installed_content(
                    course_id,
                    vid,
                    home,
                )
                if verification.get("user_modified") and not force_modified:
                    protected = True
            refs.append(
                InstalledVersionRef(
                    course_id=course_id,
                    version_id=vid,
                    version=version_label,
                    installed_at=installed_at,
                    protected=protected,
                    path=version_dir,
                )
            )

        refs.sort(key=lambda r: r.installed_at, reverse=True)

        non_protected = [r for r in refs if not r.protected]
        protected_refs = [r for r in refs if r.protected]

        keep_non = non_protected[: max(keep, 0)]
        remove_non = non_protected[max(keep, 0) :]

        keep_tuple = tuple(keep_non + protected_refs)
        remove_tuple = tuple(remove_non)

        return RetentionPlan(
            course_id=course_id,
            keep=keep_tuple,
            remove=remove_tuple,
            reason=(
                f"keep {len(keep_tuple)} versions, "
                f"remove {len(remove_tuple)} versions "
                f"(keep={keep})"
            ),
        )

    def apply(
        self,
        plan: RetentionPlan,
        *,
        dry_run: bool = True,
    ) -> RetentionPlan:
        """Delete directories of removed versions and rebuild indexes."""
        if not plan.remove:
            return plan
        if dry_run:
            return plan

        home: Path = self._state.home
        deleted: list[InstalledVersionRef] = []
        for ref in plan.remove:
            try:
                if ref.path.is_dir():
                    shutil.rmtree(ref.path)
                    deleted.append(ref)
            except OSError:
                pass

        if deleted:
            with contextlib.suppress(OSError):
                write_index(build_index(home), home)
            try:
                entries = build_recall_entries(
                    list_installed(home), read_workflows(home)
                )
                write_recall(entries, home)
            except OSError:
                pass

        return plan

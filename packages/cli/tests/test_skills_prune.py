# SPDX-License-Identifier: MIT
"""Tests for ``logion skills prune`` and the retention engine."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cli._local_state import (
    ensure_layout,
    list_installed,
    read_index,
    read_recall,
    write_manifest,
    write_workflows,
)
from cli.commands.skills.prune import (
    DEFAULT_KEEP,
    InstalledVersionRetention,
    LocalState,
    handle_skills_prune,
)

COURSE_ID = "retention.test.course"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return ensure_layout(tmp_path / "logion-test")


def _make_manifest(
    course_id: str = COURSE_ID,
    version_id: str = "v1",
    title: str = "Retention Test",
    installed_at: str = "2026-01-01T00:00:00Z",
    content_sha256: str = "abc123",
    **overrides: object,
) -> dict:
    base: dict = {
        "course_id": course_id,
        "version_id": version_id,
        "title": title,
        "source": "logion-marketplace",
        "installed_at": installed_at,
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal"],
        "content_sha256": content_sha256,
        "review_status": "approved",
        "entitlement_status": "active",
        "license_scope": "unknown",
        "official_update_channel": True,
        "last_verified_at": None,
        "manifest_path": "/tmp/placeholder/manifest.json",
    }
    base.update(overrides)
    return base


def _install_version(
    home: Path,
    course_id: str,
    version_id: str,
    installed_at: datetime,
    content: str = "hello",
    content_sha256: str | None = None,
) -> Path:
    """Write a manifest + SKILL.md for one version."""
    from cli.commands.skills._install_helpers import (
        collect_installable_files,
        compute_content_hash,
    )

    version_dir = home / "installed" / course_id / version_id
    version_dir.mkdir(parents=True, exist_ok=True)
    skill_md = version_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")

    if content_sha256 is None:
        content_sha256 = compute_content_hash(
            collect_installable_files(version_dir),
            root=version_dir,
        )

    manifest = _make_manifest(
        course_id=course_id,
        version_id=version_id,
        installed_at=installed_at.isoformat(),
        content_sha256=content_sha256,
    )
    write_manifest(manifest, course_id, version_id, home)
    return version_dir


def _ns(
    target: Path | None = None,
    course_id: str = COURSE_ID,
    keep: int = DEFAULT_KEEP,
    yes: bool = False,
    dry_run: bool = False,
    force_modified: bool = False,
    json_output: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        target=target,
        course_id=course_id,
        keep=keep,
        yes=yes,
        dry_run=dry_run,
        force_modified=force_modified,
        json_output=json_output,
    )


# ---------------------------------------------------------------------------
# Retention planning
# ---------------------------------------------------------------------------


def test_retention_keeps_active_and_two_recent(home: Path) -> None:
    """With 5 versions and keep=3, the active version is always kept."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        _install_version(
            home,
            COURSE_ID,
            f"v{i + 1}",
            base + timedelta(days=i),
            content=f"content-v{i + 1}",
        )

    # Mark v3 as the active version in index.json.
    from cli._local_state import (
        _write_json_entries,  # type: ignore[import-private]
    )

    index_entry = {
        "course_id": COURSE_ID,
        "version_id": "v3",
        "title": "Retention Test",
        "source": "logion-marketplace",
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal"],
        "review_status": "approved",
        "entitlement_status": "active",
        "license_scope": "unknown",
        "official_update_channel": True,
        "last_verified_at": None,
        "manifest_path": str(
            home / "installed" / COURSE_ID / "v3" / "manifest.json"
        ),
    }
    _write_json_entries(home / "index.json", [index_entry])

    state = LocalState(home)
    retention = InstalledVersionRetention(state)
    plan = retention.plan(COURSE_ID, keep=3)

    active_refs = [r for r in plan.keep if r.version_id == "v3"]
    assert len(active_refs) == 1, "active version v3 must be kept"
    assert active_refs[0].protected

    # With keep=3 and 1 protected (active v3), there are 4
    # non-protected. keep=3 means keep 3 non-protected + 1
    # protected = 4, remove 1 (the oldest non-protected).
    assert len(plan.remove) == 1
    removed_vid = plan.remove[0].version_id
    assert removed_vid == "v1", "oldest non-protected should be removed"


def test_retention_preserves_workflow_referenced_version(
    home: Path,
) -> None:
    """A version referenced by workflows.json is protected."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(4):
        _install_version(
            home,
            COURSE_ID,
            f"v{i + 1}",
            base + timedelta(days=i),
        )

    # Reference v1 (oldest) in workflows.json.
    write_workflows(
        [
            {
                "id": "wf-1",
                "title": "Test Workflow",
                "commands": ["echo hello"],
                "success_count": 1,
                "last_success_at": "2026-01-02T00:00:00Z",
                "confidence": 0.9,
                "course_id": COURSE_ID,
                "version_id": "v1",
            }
        ],
        home,
    )

    state = LocalState(home)
    retention = InstalledVersionRetention(state)
    plan = retention.plan(COURSE_ID, keep=1)

    v1_refs = [r for r in plan.keep if r.version_id == "v1"]
    assert len(v1_refs) == 1, "workflow-referenced v1 must be kept"
    assert v1_refs[0].protected
    assert all(r.version_id != "v1" for r in plan.remove), (
        "v1 must not be in remove set"
    )


def test_retention_preserves_modified_version_without_force(
    home: Path,
) -> None:
    """A locally modified version is protected without --force-modified."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    # Install v1 with a known content hash, then modify the file.
    _install_version(
        home,
        COURSE_ID,
        "v1",
        base,
        content="original",
        content_sha256="a" * 64,
    )
    # Modify the on-disk content so the hash diverges.
    skill_md = home / "installed" / COURSE_ID / "v1" / "SKILL.md"
    skill_md.write_text("modified", encoding="utf-8")

    for i in range(2, 5):
        _install_version(
            home,
            COURSE_ID,
            f"v{i}",
            base + timedelta(days=i),
        )

    state = LocalState(home)
    retention = InstalledVersionRetention(state)
    plan = retention.plan(COURSE_ID, keep=1)

    v1_refs = [r for r in plan.keep if r.version_id == "v1"]
    assert len(v1_refs) == 1, "modified v1 must be kept without force"
    assert v1_refs[0].protected
    assert all(r.version_id != "v1" for r in plan.remove), (
        "modified v1 must not be in remove set"
    )


# ---------------------------------------------------------------------------
# CLI handler
# ---------------------------------------------------------------------------


def test_skills_prune_dry_run_does_not_delete(home: Path) -> None:
    """Dry run does not delete files."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        _install_version(
            home,
            COURSE_ID,
            f"v{i + 1}",
            base + timedelta(days=i),
        )

    rc = handle_skills_prune(
        _ns(target=home, course_id=COURSE_ID, keep=1, dry_run=True)
    )

    assert rc == 0
    for i in range(1, 6):
        version_dir = home / "installed" / COURSE_ID / f"v{i}"
        assert version_dir.exists(), f"v{i} must still exist after dry run"


def test_skills_prune_rebuilds_index_and_recall_after_delete(
    home: Path,
) -> None:
    """After deletion with --yes, index and recall are rebuilt."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        _install_version(
            home,
            COURSE_ID,
            f"v{i + 1}",
            base + timedelta(days=i),
        )

    # Build initial index and recall.
    from cli._local_state import (
        build_index,
        build_recall_entries,
        write_index,
        write_recall,
    )

    write_index(build_index(home), home)
    write_recall(
        build_recall_entries(list_installed(home), read_recall(home)),
        home,
    )

    initial_installed = list_installed(home)
    assert len(initial_installed) == 5

    rc = handle_skills_prune(
        _ns(target=home, course_id=COURSE_ID, keep=1, yes=True)
    )

    assert rc == 0
    remaining = list_installed(home)
    # With keep=1, 1 non-protected kept + any protected. No active or
    # workflow-referenced versions here, so remove=4, keep=1.
    assert len(remaining) <= 2, (
        f"expected at most 2 remaining, got {len(remaining)}"
    )

    # index.json and recall.json should reflect the current state.
    index_entries = read_index(home)
    assert len(index_entries) == len(remaining)

    recall_entries = read_recall(home)
    installed_recall = [
        e
        for e in recall_entries
        if e.get("type") == "installed_capability" and e.get("id") == COURSE_ID
    ]
    assert len(installed_recall) == len(remaining)

# SPDX-License-Identifier: MIT
"""Handlers for the workspace command group."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from cli._errors import print_err, validate_uuid_id
from cli._json import JsonArray, JsonObject
from cli._output import emit

from ._state import (
    has_dirty_files,
    now_iso,
    read_json,
    resolve_workspace,
    write_json_atomic,
)


def handle_init(args: argparse.Namespace) -> int:
    """Create the workspace directory structure and an empty ``state.json``."""
    root = resolve_workspace(args.workspace or args.path)
    # Create directory scaffold
    (root / "current").mkdir(parents=True, exist_ok=True)
    (root / "submissions").mkdir(parents=True, exist_ok=True)
    # Write empty state
    state_path = root / "state.json"
    if state_path.exists() and not args.force:
        print_err("Error: state.json exists. Use --force.")
        return 2
    state: JsonObject = {
        "active_bounty_id": None,
        "active_submission_id": None,
        "current_path": str(root / "current"),
        "updated_at": now_iso(),
    }
    write_json_atomic(state_path, state)
    emit(state, json_output=getattr(args, "json_output", False))
    return 0


def handle_status(args: argparse.Namespace) -> int:
    """Print the current workspace state."""
    root = resolve_workspace(args.workspace)
    state_path = root / "state.json"
    if not state_path.exists():
        print_err("Error: workspace not initialised. Run init first.")
        return 2
    state = read_json(state_path)
    emit(state, json_output=getattr(args, "json_output", False))
    return 0


def _archive_current(root: Path) -> None:
    """Move the contents of ``current/`` into the active submission directory.

    If there is no active submission, ``current/`` is simply cleared.
    """
    state = read_json(root / "state.json")
    current_dir = root / "current"
    bounty_id = state.get("active_bounty_id")
    submission_id = state.get("active_submission_id")

    if bounty_id and submission_id:
        dest = root / "submissions" / str(submission_id)
        dest.mkdir(parents=True, exist_ok=True)
        # Move files into the submission's ``files/`` subdirectory
        files_dir = dest / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        for item in current_dir.iterdir():
            if item.is_file() or item.is_dir():
                shutil.move(str(item), str(files_dir / item.name))
    else:
        # No active submission — just clear current/
        for item in current_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()


def handle_checkout(args: argparse.Namespace) -> int:
    """Materialize a submission into ``current/``."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.submission_id, "SUBMISSION_ID")
    if bad_id is not None:
        return bad_id
    root = resolve_workspace(args.workspace)
    state_path = root / "state.json"
    if not state_path.exists():
        print_err("Error: workspace not initialised. Run init first.")
        return 2

    current_dir = root / "current"
    # Dirty check (unless --force)
    if not args.force and has_dirty_files(current_dir):
        print_err(
            "Error: current/ has uncommitted files. "
            "Commit them or use --force to overwrite."
        )
        return 2

    # Archive existing work if there is an active submission
    _archive_current(root)

    bounty_id = args.bounty_id
    submission_id = args.submission_id

    # Ensure submission directory exists
    submission_dir = root / "submissions" / str(submission_id)
    submission_dir.mkdir(parents=True, exist_ok=True)

    # Write metadata for the new submission
    meta: JsonObject = {
        "bounty_id": bounty_id,
        "submission_id": submission_id,
        "title": getattr(args, "title", None),
        "description": getattr(args, "description", None),
        "remote_status": "checked_out",
        "checked_out_at": now_iso(),
    }
    write_json_atomic(submission_dir / "metadata.json", meta)

    # Materialize files from submission into current/
    src_files = submission_dir / "files"
    if src_files.exists():
        for item in src_files.iterdir():
            target = current_dir / item.name
            if item.is_file():
                shutil.copy2(str(item), str(target))
            elif item.is_dir():
                if target.exists():
                    shutil.rmtree(str(target))
                shutil.copytree(str(item), str(target))

    # Update state
    state = read_json(state_path)
    state["active_bounty_id"] = bounty_id
    state["active_submission_id"] = submission_id
    state["current_path"] = str(current_dir)
    state["updated_at"] = now_iso()
    write_json_atomic(state_path, state)

    emit(state, json_output=getattr(args, "json_output", False))
    return 0


def handle_switch(args: argparse.Namespace) -> int:
    """Switch to a different submission.

    Without ``--force``, archives current work before switching
    (refuses if there are dirty files). With ``--force``, discards
    dirty files and switches unconditionally.
    """
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.submission_id, "SUBMISSION_ID")
    if bad_id is not None:
        return bad_id
    root = resolve_workspace(args.workspace)
    state_path = root / "state.json"
    if not state_path.exists():
        print_err("Error: workspace not initialised. Run init first.")
        return 2

    current_dir = root / "current"
    if not args.force and has_dirty_files(current_dir):
        print_err(
            "Error: current/ has uncommitted files. "
            "Commit them or use --force to discard."
        )
        return 2

    if args.force:
        # --force discards dirty files without archiving
        for item in current_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        # Archive before switching (preserving dirty files)
        _archive_current(root)

    # Delegate the rest to checkout logic (re-parse args namespace)
    args_bak = args.force
    args.force = True  # already archived, skip dirty check
    rc = handle_checkout(args)
    args.force = args_bak
    return rc


def handle_evidence(args: argparse.Namespace) -> int:
    """Walk ``current/`` and build an evidence JSON manifest."""
    root = resolve_workspace(args.workspace)
    state_path = root / "state.json"
    if not state_path.exists():
        print_err("Error: workspace not initialised. Run init first.")
        return 2
    current_dir = root / "current"

    evidence: JsonObject = {
        "generated_at": now_iso(),
    }
    files: JsonArray = []
    for item in sorted(current_dir.rglob("*")):
        if item.is_file():
            rel = item.relative_to(current_dir)
            files.append({
                "path": str(rel),
                "size": item.stat().st_size,
            })
    evidence["files"] = files

    output_path = Path(args.output) if args.output else root / "evidence.json"
    write_json_atomic(output_path, evidence)
    emit(evidence, json_output=getattr(args, "json_output", False))
    return 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

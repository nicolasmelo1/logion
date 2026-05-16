"""Local bounty workspace management."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cli._output import emit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class UserError(Exception):
    """Raised when a local precondition is not met (e.g. dirty workspace)."""


def _print_err(msg: str) -> None:
    """Print a user-facing message to stderr."""
    import sys

    print(msg, file=sys.stderr)


def has_dirty_files(path: Path) -> bool:
    """Return ``True`` if *path* contains any regular files (recursively)."""
    return any(item.is_file() for item in path.rglob("*"))


def write_json_atomic(path: Path, data: dict[str, object]) -> None:
    """Write *data* as JSON to *path* atomically via a temp file."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.rename(path)


def _read_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file, or return an empty dict on failure."""
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _resolve_workspace(workspace: str | None) -> Path:
    """Resolve the workspace root directory.

    If *workspace* is given (via ``--workspace``), use it directly.
    Otherwise default to ``.logion/bounty-workspace`` relative to cwd.
    """
    if workspace is not None:
        return Path(workspace).resolve()
    return (Path.cwd() / ".logion" / "bounty-workspace").resolve()


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def _handle_init(args: argparse.Namespace) -> int:
    """Create the workspace directory structure and an empty ``state.json``."""
    root = _resolve_workspace(args.path)
    # Create directory scaffold
    (root / "current").mkdir(parents=True, exist_ok=True)
    (root / "submissions").mkdir(parents=True, exist_ok=True)
    # Write empty state
    state_path = root / "state.json"
    if state_path.exists() and not args.force:
        _print_err("Error: state.json exists. Use --force.")
        return 2
    state: dict[str, object] = {
        "active_bounty_id": None,
        "active_submission_id": None,
        "current_path": str(root / "current"),
        "updated_at": _now_iso(),
    }
    write_json_atomic(state_path, state)
    emit(state, json_output=getattr(args, "json_output", False))
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    """Print the current workspace state."""
    root = _resolve_workspace(args.workspace)
    state_path = root / "state.json"
    if not state_path.exists():
        _print_err("Error: workspace not initialised. Run init first.")
        return 2
    state = _read_json(state_path)
    emit(state, json_output=getattr(args, "json_output", False))
    return 0


def _archive_current(root: Path) -> None:
    """Move the contents of ``current/`` into the active submission directory.

    If there is no active submission, ``current/`` is simply cleared.
    """
    state = _read_json(root / "state.json")
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


def _handle_checkout(args: argparse.Namespace) -> int:
    """Materialize a submission into ``current/``."""
    root = _resolve_workspace(args.workspace)
    state_path = root / "state.json"
    if not state_path.exists():
        _print_err("Error: workspace not initialised. Run init first.")
        return 2

    current_dir = root / "current"
    # Dirty check (unless --force)
    if not args.force and has_dirty_files(current_dir):
        _print_err(
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
    meta: dict[str, object] = {
        "bounty_id": bounty_id,
        "submission_id": submission_id,
        "title": getattr(args, "title", None),
        "description": getattr(args, "description", None),
        "remote_status": "checked_out",
        "checked_out_at": _now_iso(),
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
    state = _read_json(state_path)
    state["active_bounty_id"] = bounty_id
    state["active_submission_id"] = submission_id
    state["current_path"] = str(current_dir)
    state["updated_at"] = _now_iso()
    write_json_atomic(state_path, state)

    emit(state, json_output=getattr(args, "json_output", False))
    return 0


def _handle_switch(args: argparse.Namespace) -> int:
    """Archive current work and check out a different submission.

    This is identical to ``checkout`` but always archives first (i.e. it
    refuses to run if there are dirty files — use ``--force`` to discard).
    """
    root = _resolve_workspace(args.workspace)
    state_path = root / "state.json"
    if not state_path.exists():
        _print_err("Error: workspace not initialised. Run init first.")
        return 2

    current_dir = root / "current"
    if not args.force and has_dirty_files(current_dir):
        _print_err(
            "Error: current/ has uncommitted files. "
            "Commit them or use --force to discard."
        )
        return 2

    # Archive before switching
    _archive_current(root)
    # Clear current/ so the checkout starts clean
    for item in current_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # Delegate the rest to checkout logic (re-parse args namespace)
    args_bak = args.force
    args.force = True  # already archived, skip dirty check
    rc = _handle_checkout(args)
    args.force = args_bak
    return rc


def _handle_evidence(args: argparse.Namespace) -> int:
    """Walk ``current/`` and build an evidence JSON manifest."""
    root = _resolve_workspace(args.workspace)
    current_dir = root / "current"
    if not current_dir.exists():
        _print_err("Error: workspace not initialised. Run init first.")
        return 2

    evidence: dict[str, Any] = {
        "files": [],
        "generated_at": _now_iso(),
    }
    for item in sorted(current_dir.rglob("*")):
        if item.is_file():
            rel = item.relative_to(current_dir)
            evidence["files"].append({
                "path": str(rel),
                "size": item.stat().st_size,
            })

    output_path = Path(args.output) if args.output else root / "evidence.json"
    write_json_atomic(output_path, evidence)
    emit(evidence, json_output=getattr(args, "json_output", False))
    return 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``workspace`` subcommand group."""
    parser = subparsers.add_parser(
        "workspace",
        help="Local bounty workspace management",
    )
    sub = parser.add_subparsers(
        dest="workspace_command",
        required=True,
    )

    # ── init ────────────────────────────────────────────────────
    init = sub.add_parser("init", help="Initialise a new bounty workspace")
    init.add_argument(
        "--path",
        default=None,
        help="Workspace root (default: .logion/bounty-workspace)",
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing state.json",
    )
    init.set_defaults(handler=_handle_init)

    # ── status ─────────────────────────────────────────────────
    status = sub.add_parser("status", help="Print current workspace state")
    status.add_argument(
        "--workspace",
        default=None,
        help="Workspace root (default: .logion/bounty-workspace)",
    )
    status.set_defaults(handler=_handle_status)

    # ── checkout ────────────────────────────────────────────────
    checkout = sub.add_parser("checkout", help="Check out a bounty submission")
    checkout.add_argument("bounty_id", help="Bounty UUID")
    checkout.add_argument("submission_id", help="Submission UUID")
    checkout.add_argument(
        "--workspace",
        default=None,
        help="Workspace root (default: .logion/bounty-workspace)",
    )
    checkout.add_argument(
        "--force",
        action="store_true",
        help="Overwrite dirty files in current/",
    )
    checkout.set_defaults(handler=_handle_checkout)

    # ── switch ──────────────────────────────────────────────────
    switch = sub.add_parser(
        "switch",
        help="Archive current and check out another submission",
    )
    switch.add_argument("bounty_id", help="Bounty UUID")
    switch.add_argument("submission_id", help="Submission UUID")
    switch.add_argument(
        "--workspace",
        default=None,
        help="Workspace root (default: .logion/bounty-workspace)",
    )
    switch.add_argument(
        "--force",
        action="store_true",
        help="Discard dirty files in current/",
    )
    switch.set_defaults(handler=_handle_switch)

    # ── evidence ────────────────────────────────────────────────
    evidence = sub.add_parser(
        "evidence",
        help="Build an evidence manifest from current/",
    )
    evidence.add_argument(
        "--workspace",
        default=None,
        help="Workspace root (default: .logion/bounty-workspace)",
    )
    evidence.add_argument(
        "--output",
        default=None,
        help=(
            "Output path for evidence JSON"
            " (default: <workspace>/evidence.json)"
        ),
    )
    evidence.set_defaults(handler=_handle_evidence)

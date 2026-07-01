# SPDX-License-Identifier: MIT
"""Handler for ``logion skills prune``.

Delegates retention logic to :mod:`_prune_engine`.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict

from cli._errors import emit_error_json
from cli._local_state import UnsafeIdentifierError, _safe_segment
from cli._output import emit_json

from ._install_helpers import resolve_target
from ._prune_engine import (
    DEFAULT_KEEP,
    InstalledVersionRef,
    InstalledVersionRetention,
    LocalState,
    RetentionPlan,
)

__all__ = [
    "DEFAULT_KEEP",
    "InstalledVersionRef",
    "InstalledVersionRetention",
    "LocalState",
    "RetentionPlan",
    "handle_skills_prune",
]


def _ref_to_dict(ref: InstalledVersionRef) -> dict:
    """Convert a ref to a JSON-safe dict (datetime/path -> str)."""
    d = asdict(ref)
    d["installed_at"] = ref.installed_at.isoformat()
    d["path"] = str(ref.path)
    return d


def _plan_to_dict(plan: RetentionPlan) -> dict:
    return {
        "course_id": plan.course_id,
        "keep": [_ref_to_dict(r) for r in plan.keep],
        "remove": [_ref_to_dict(r) for r in plan.remove],
        "reason": plan.reason,
    }


def _error(
    args: argparse.Namespace,
    code: str,
    message: str,
    exit_code: int,
) -> int:
    """Emit a compliant error in JSON or human form."""
    if getattr(args, "json_output", False):
        emit_error_json(code, message, exit_code)
    else:
        print(f"Error: {message}", file=sys.stderr)
    return exit_code


def handle_skills_prune(args: argparse.Namespace) -> int:
    """Prune old installed versions for a course.

    Defaults to dry-run unless ``--yes`` is passed.
    """
    home = resolve_target(args)
    course_id: str = getattr(args, "course_id", "")
    keep: int = getattr(args, "keep", DEFAULT_KEEP)
    dry_run = not bool(getattr(args, "yes", False))
    force_modified = bool(getattr(args, "force_modified", False))
    json_output = bool(getattr(args, "json_output", False))

    if not course_id:
        return _error(
            args,
            "validation_failed",
            "course_id is required",
            2,
        )

    if getattr(args, "dry_run", False) and getattr(args, "yes", False):
        return _error(
            args,
            "validation_failed",
            "--dry-run and --yes are mutually exclusive",
            2,
        )

    try:
        _safe_segment(course_id, "course_id")
    except UnsafeIdentifierError as exc:
        return _error(args, "unsafe_identifier", str(exc), 2)

    state = LocalState(home)
    retention = InstalledVersionRetention(state)
    plan = retention.plan(
        course_id,
        keep=keep,
        force_modified=force_modified,
    )
    plan = retention.apply(plan, dry_run=dry_run)

    payload = _plan_to_dict(plan)
    payload["dry_run"] = dry_run

    if json_output:
        emit_json("logion.skills.prune", payload)
        return 0

    if dry_run:
        print(f"Prune plan for {course_id} (dry-run):")
    else:
        print(f"Pruned {course_id}:")
    print(f"  keep {len(plan.keep)}, remove {len(plan.remove)}")
    if plan.remove:
        print("  Removed:")
        for ref in plan.remove:
            print(f"    {ref.version_id}")
    else:
        print("  Nothing to remove.")
    return 0

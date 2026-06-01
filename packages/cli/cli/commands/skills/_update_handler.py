# SPDX-License-Identifier: MIT
"""Handler for ``logion skills update``.

Kept separate from :mod:`handlers` so each file stays under the CLI's
per-source-file line budget.  See :func:`handle_skills_update` for the
control flow; the policy primitives live in :mod:`cli._update_policy`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from cli._local_state import read_manifest
from cli._update_policy import evaluate_update

from ._install_helpers import read_capabilities, resolve_target


def _build_remote_manifest(
    source: Path,
    course_id: str,
    version_id: str,
    title: str | None,
) -> dict[str, Any]:
    """Synthesize a candidate manifest from a local source bundle.

    The marketplace API is not in the loop for this flow — the
    "remote" manifest is the one we *would* write if this install
    proceeded.  ``evaluate_update`` diffs it against the installed
    manifest to decide whether the change requires approval.
    """
    manifest: dict[str, Any] = {
        "course_id": course_id,
        "version_id": version_id,
        "title": title or "",
        "entrypoint": "SKILL.md",
        "capabilities": [],
        "required_tools": ["terminal", "file"],
        "permissions": [],
        "env_vars": [],
        "execution_policy": "approval-required",
        "review_status": "approved",
    }
    return read_capabilities(source / "course" / "capabilities.yaml", manifest)


def handle_skills_update(args: argparse.Namespace) -> int:
    """Apply an update with safety policy.

    Diffs the installed manifest against the candidate manifest from
    *source* via :func:`evaluate_update`.  If any gated field
    (permissions, required tools, env vars, execution policy) changed
    or the local content was modified, refuses unless ``--force`` is
    passed.  Otherwise delegates to the install handler.
    """
    # Import here to avoid a circular import; handlers imports from
    # this module via the parser registration.
    from .handlers import handle_skills_install

    home = resolve_target(args)
    course_id: str = args.course_id
    version_id: str = args.version_id

    local_manifest = read_manifest(course_id, version_id, home)
    if local_manifest is None:
        print(
            f"ERROR: no installed manifest for {course_id}/{version_id}; "
            "use `logion skills install` first.",
            file=sys.stderr,
        )
        return 1

    remote_manifest = _build_remote_manifest(
        args.source.resolve(),
        course_id,
        version_id,
        getattr(args, "title", None),
    )
    policy = evaluate_update(
        course_id, version_id, remote_manifest, local_manifest, home
    )

    if policy.notices:
        for note in policy.notices:
            print(f"NOTICE: {note}", file=sys.stderr)

    blocked = policy.requires_approval or policy.blocks_silent_overwrite
    if blocked and not args.force:
        print(
            f"Refusing to update {course_id}/{version_id} without approval:",
            file=sys.stderr,
        )
        for reason in policy.reasons:
            print(f"  - {reason}", file=sys.stderr)
        print("Pass --force to apply.", file=sys.stderr)
        return 2

    install_args = argparse.Namespace(
        source=args.source,
        course_id=course_id,
        version_id=version_id,
        title=getattr(args, "title", None),
        target=getattr(args, "target", None),
        dry_run=False,
        force=True,
    )
    return handle_skills_install(install_args)

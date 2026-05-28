"""Handler for ``logion skills verify``.

Kept separate from :mod:`handlers` so each file stays under the CLI's
per-source-file line budget.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from cli._local_state import (
    UnsafeIdentifierError,
    _safe_segment,
    _utc_iso_now,
    list_installed,
    read_manifest,
    write_manifest,
)
from cli._output import emit_json

from ._install_helpers import resolve_target


def handle_skills_verify(args: argparse.Namespace) -> int:
    """Re-check entitlement status for installed skills.

    For now this is a local-only check: the manifest exists means
    ``entitlement_status`` is set to ``"active"``, otherwise ``"missing"``.
    ``last_verified_at`` is always updated to the current UTC timestamp.
    When a real entitlements API is available this handler will call it.
    """
    home = resolve_target(args)
    course_id: str | None = getattr(args, "course_id", None)

    if course_id is not None:
        try:
            _safe_segment(course_id, "course_id")
        except UnsafeIdentifierError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    installed = list_installed(home)
    if course_id is not None:
        installed = [m for m in installed if m.get("course_id") == course_id]

    results: list[dict[str, Any]] = []
    now = _utc_iso_now()

    for m in installed:
        cid = m.get("course_id", "?")
        vid = m.get("version_id", "?")
        # Local verification: manifest present → "active",
        # absent → "missing"
        manifest = read_manifest(cid, vid, home)
        if manifest is not None:
            m["entitlement_status"] = "active"
            m["last_verified_at"] = now
            write_manifest(m, cid, vid, home)
        else:
            m["entitlement_status"] = "missing"
            m["last_verified_at"] = now
        results.append({
            "course_id": cid,
            "entitlement_status": m["entitlement_status"],
            "last_verified_at": m["last_verified_at"],
        })

    if getattr(args, "json_output", False):
        emit_json("logion.skills.verify", results)
        return 0

    if not results:
        print("No installed skills to verify.")
        return 0

    print(f"Verification results ({len(results)} skill(s)):")
    for entry in results:
        print(
            f"  {entry['course_id']}: "
            f"entitlement={entry['entitlement_status']}, "
            f"verified_at={entry['last_verified_at']}"
        )
    return 0

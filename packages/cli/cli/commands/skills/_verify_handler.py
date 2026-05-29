"""Handler for ``logion skills verify``.

Kept separate from :mod:`handlers` so each file stays under the CLI's
per-source-file line budget.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from cli._errors import emit_error_json
from cli._local_state import (
    VALID_ENTITLEMENT_STATUSES,
    UnsafeIdentifierError,
    _safe_segment,
    _utc_iso_now,
    list_installed,
    write_manifest,
)
from cli._output import emit_json

from ._install_helpers import resolve_target


def _error(
    args: argparse.Namespace, code: str, message: str, exit_code: int
) -> int:
    """Emit a compliant error in JSON or human form."""
    if getattr(args, "json_output", False):
        emit_error_json(code, message, exit_code)
    else:
        print(f"ERROR: {message}", file=sys.stderr)
    return exit_code


def _local_verify_status(manifest: dict[str, Any]) -> str:
    """Best-effort verification using only public SDK-local data.

    The current public SDK exposes checkout/order state but no dedicated
    entitlements endpoint, so verification cannot prove fresh ownership
    server-side in this repository alone. We therefore preserve a known
    marketplace entitlement state, while manual installs remain unknown.
    """
    source = manifest.get("source")
    current = manifest.get("entitlement_status")
    if source != "logion-marketplace":
        return "unknown"
    if current in VALID_ENTITLEMENT_STATUSES:
        return str(current)
    return "unknown"


def handle_skills_verify(args: argparse.Namespace) -> int:
    """Refresh local entitlement metadata for installed skills."""
    home = resolve_target(args)
    course_id: str | None = getattr(args, "course_id", None)

    if course_id is not None:
        try:
            _safe_segment(course_id, "course_id")
        except UnsafeIdentifierError as exc:
            return _error(args, "unsafe_identifier", str(exc), 1)

    installed = list_installed(home)
    if course_id is not None:
        installed = [m for m in installed if m.get("course_id") == course_id]

    results: list[dict[str, Any]] = []
    now = _utc_iso_now()

    for manifest in installed:
        cid = str(manifest.get("course_id", "?"))
        vid = str(manifest.get("version_id", "?"))
        manifest["entitlement_status"] = _local_verify_status(manifest)
        manifest["last_verified_at"] = now
        write_manifest(manifest, cid, vid, home)
        results.append({
            "course_id": cid,
            "entitlement_status": manifest["entitlement_status"],
            "last_verified_at": manifest["last_verified_at"],
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

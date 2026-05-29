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
    """Preserve the locally recorded entitlement status.

    The public SDK currently exposes no entitlements read endpoint, so this
    command cannot prove fresh server-side ownership. Marketplace installs keep
    their stored entitlement state; non-marketplace installs remain unknown.
    """
    source = manifest.get("source")
    current = manifest.get("entitlement_status")
    if source != "logion-marketplace":
        return "unknown"
    if current in VALID_ENTITLEMENT_STATUSES:
        return str(current)
    return "unknown"


def _verification_mode(_manifest: dict[str, Any]) -> str:
    """Return the verification mode reported to callers."""
    return "local-manifest-only"


def handle_skills_verify(args: argparse.Namespace) -> int:
    """Refresh locally stored entitlement metadata for installed skills."""
    home = resolve_target(args)
    course_id: str | None = getattr(args, "course_id", None)

    if course_id is not None:
        try:
            _safe_segment(course_id, "course_id")
        except UnsafeIdentifierError as exc:
            return _error(args, "unsafe_identifier", str(exc), 2)

    installed = list_installed(home)
    if course_id is not None:
        installed = [m for m in installed if m.get("course_id") == course_id]

    results: list[dict[str, Any]] = []

    for manifest in installed:
        cid = str(manifest.get("course_id", "?"))
        vid = str(manifest.get("version_id", "?"))
        new_status = _local_verify_status(manifest)
        old_status = manifest.get("entitlement_status")
        manifest["entitlement_status"] = new_status
        if new_status != old_status:
            write_manifest(manifest, cid, vid, home)
        results.append({
            "course_id": cid,
            "entitlement_status": new_status,
            "last_verified_at": manifest.get("last_verified_at"),
            "source": manifest.get("source", "unknown"),
            "verification_mode": _verification_mode(manifest),
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
            f"mode={entry['verification_mode']}, "
            f"source={entry['source']}, "
            f"last_verified_at={entry['last_verified_at']}"
        )
    return 0

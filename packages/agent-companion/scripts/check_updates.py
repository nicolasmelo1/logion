#!/usr/bin/env python3
"""Check for available updates to installed Logion capabilities.

Now supports update-policy safety gates:

- Checking update availability is always allowed.
- Downloading metadata is always allowed.
- Applying an update requires approval when content changes.
- Applying an update ALWAYS requires approval when price,
  permissions, required_tools, or execution policy changes.
- Never silently overwrite a user-modified local artifact.

Usage:
    python scripts/check_updates.py [OPTIONS]

Options:
    --target PATH   Override LOGION_HOME (default: ~/.logion)
    --dry-run       Show what would be checked without network calls
    --help          Show this help message
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from logion_agent_companion.local_state import (
    ensure_layout,
    list_installed,
    validate_manifest,
)

# ---------------------------------------------------------------------------
# Update policy
# ---------------------------------------------------------------------------

SAFE_AUTO_CHECK_FIELDS = frozenset({
    "available_version",
    "changelog_summary",
})

REQUIRES_APPROVAL_IF_CHANGED = frozenset({
    "price_cents_at_install",
    "currency",
    "capabilities",
    "required_tools",
})

ALWAYS_REQUIRES_APPROVAL_FIELDS = frozenset({
    "execution_policy",
    "permissions",
})

MASQUERADE_FIELDS = frozenset({
    "apikey",
    "auth_token",
    "secret",
    "token",
    "password",
    "credential",
})


def detect_permission_expansion(
    old: dict[str, Any],
    new: dict[str, Any],
) -> list[str]:
    """Return a list of fields that expanded permissions or scope."""
    expansions: list[str] = []
    for field in REQUIRES_APPROVAL_IF_CHANGED:
        old_val = old.get(field)
        new_val = new.get(field)
        if old_val != new_val and new_val is not None:
            expansions.append(field)
    for field in ALWAYS_REQUIRES_APPROVAL_FIELDS:
        if field in new and new[field] != old.get(field):
            expansions.append(field)
    return expansions


def check_update_policy(
    old_manifest: dict[str, Any],
    new_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate whether an update can be applied without approval.

    Returns a dict with:
    - ``requires_approval``: bool — whether explicit approval is needed.
    - ``reasons``: list[str] — human-readable reasons for requiring approval.
    - ``permission_expansions``: list[str] — fields that changed scope.
    """
    requires_approval = False
    reasons: list[str] = []

    # Content change always requires approval
    old_hash = old_manifest.get("content_sha256", "")
    new_hash = new_manifest.get("content_sha256", "")
    if old_hash and new_hash and old_hash != new_hash:
        requires_approval = True
        reasons.append("content_sha256 changed")

    # Price change requires approval
    old_price = old_manifest.get("price_cents_at_install", 0)
    new_price = new_manifest.get("price_cents_at_install", 0)
    if old_price != new_price:
        requires_approval = True
        reasons.append("price changed")

    # Permission/capability/tool changes require approval
    expansions = detect_permission_expansion(old_manifest, new_manifest)
    if expansions:
        requires_approval = True
        for field in expansions:
            reasons.append(f"{field} changed")

    return {
        "requires_approval": requires_approval,
        "reasons": reasons,
        "permission_expansions": expansions,
    }


def mask_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *data* with secret-like fields masked."""
    masked = {}
    for key, value in data.items():
        if any(term in key.lower() for term in MASQUERADE_FIELDS):
            masked[key] = "***MASKED***"
        else:
            masked[key] = value
    return masked


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def report_installed(home: Path) -> int:
    """Print installed capabilities and their update status."""
    installed = list_installed(home)
    if not installed:
        print("No installed capabilities found.")
        print(f"Expected directory: {home / 'installed'}")
        return 0

    print(f"Installed capabilities ({len(installed)}):")
    for m in installed:
        errors = validate_manifest(m)
        course_id = m.get("course_id", "?")
        version_id = m.get("version_id", "?")
        title = m.get("title", "")
        status = m.get("review_status", "unknown")
        status_line = f"  {course_id}/{version_id}"
        if title:
            status_line += f" — {title}"
        status_line += f" [{status}]"
        print(status_line)
        if errors:
            for e in errors:
                print(f"    WARNING: {e}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check for updates to installed Logion capabilities.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Override LOGION_HOME.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be checked without network calls.",
    )
    args = parser.parse_args()

    home = args.target or ensure_layout()

    if args.dry_run:
        print(f"DRY RUN: would check updates in {home}")
        installed = list_installed(home)
        print(f"  Found {len(installed)} installed capabilities.")
        return 0

    return report_installed(home)


if __name__ == "__main__":
    sys.exit(main())

"""Confirmation helper — require --yes for destructive actions."""

from __future__ import annotations

import sys


def require_yes(yes: bool, action: str) -> int | None:
    """Return ``None`` if *yes* is True, otherwise print a refusal and
    return exit code 2.
    """
    if yes:
        return None
    print(f"Refusing to {action} without --yes.", file=sys.stderr)
    return 2

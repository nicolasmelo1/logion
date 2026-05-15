"""Confirmation helper — require --yes for destructive actions."""

from __future__ import annotations

from cli._errors import print_err


def require_yes(yes: bool, action: str) -> int | None:
    """Return ``None`` if *yes* is True, otherwise print a refusal and
    return exit code 2.
    """
    if yes:
        return None
    print_err(f"Refusing to {action} without --yes.")
    return 2

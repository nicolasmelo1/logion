"""CLI error handling — map SDK errors to exit codes."""

from __future__ import annotations

import sys

from logion import APIError, LogionError


def handle_error(exc: Exception) -> int:
    """Map an exception to an exit code and print a user-facing message."""
    if isinstance(exc, APIError):
        detail = exc.detail
        if isinstance(detail, list):
            detail = "; ".join(str(d) for d in detail)
        print(f"API error {exc.status_code}: {detail}", file=sys.stderr)
        return 1
    if isinstance(exc, LogionError):
        print(f"Logion error: {exc}", file=sys.stderr)
        return 1
    raise exc

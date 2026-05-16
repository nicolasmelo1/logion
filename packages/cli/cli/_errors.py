"""CLI error handling — map SDK errors to exit codes."""

from __future__ import annotations

import sys
from uuid import UUID

# Re-export for backward compatibility; moved to _utils.py
from cli._utils import only_not_none  # noqa: F401
from logion import APIError, LogionError


def handle_error(exc: Exception) -> int:
    """Map an exception to an exit code and print a user-facing message."""
    if isinstance(exc, APIError):
        detail = getattr(exc, "detail", str(exc))
        if isinstance(detail, list):
            detail = "; ".join(str(d) for d in detail)
        status_code = getattr(exc, "status_code", "?")
        print(f"API error {status_code}: {detail}", file=sys.stderr)
        return 1
    if isinstance(exc, LogionError):
        print(f"Logion error: {exc}", file=sys.stderr)
        return 1
    raise exc


def print_err(msg: str) -> None:
    """Print a user-facing message to stderr."""
    print(msg, file=sys.stderr)


def require_non_empty_id(value: str, label: str) -> int | None:
    """Return ``2`` if *value* is empty/whitespace, else ``None``."""
    if not value or not value.strip():
        print_err(f"Error: {label} must not be empty.")
        return 2
    return None


def validate_uuid(value: str, label: str) -> int | None:
    """Return ``2`` if *value* is not a valid UUID, else ``None``."""
    try:
        UUID(value)
    except ValueError:
        print_err(f"Error: {label} must be a valid UUID (got: {value!r}).")
        return 2
    return None


def validate_uuid_id(value: str, label: str) -> int | None:
    """Check *value* is non-empty and a valid UUID.

    Combines :func:`require_non_empty_id` and :func:`validate_uuid`
    into a single call for positional-ID validation.
    """
    empty = require_non_empty_id(value, label)
    if empty is not None:
        return empty
    return validate_uuid(value, label)

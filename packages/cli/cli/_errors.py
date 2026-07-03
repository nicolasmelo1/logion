# SPDX-License-Identifier: MIT
"""CLI error handling — map SDK errors to exit codes."""

from __future__ import annotations

import json
import sys
from uuid import UUID

from logion import APIError, LogionError

ALLOWED_ERROR_CODES = frozenset({
    "auth_missing",
    "entitlement_missing",
    "entitlement_expired",
    "github_identity_conflict",
    "github_oauth_unconfigured",
    "unsafe_identifier",
    "not_found",
    "validation_failed",
    "server_error",
    "confirmation_required",
    "top_up_timeout",
})


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


def emit_error_json(code: str, message: str, exit_code: int) -> None:
    """Emit a v1 JSON error envelope to stderr."""
    payload = {
        "version": "v1",
        "kind": "logion.error",
        "data": {"code": code, "message": message, "exit_code": exit_code},
    }
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)


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

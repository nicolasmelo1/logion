# SPDX-License-Identifier: MIT
"""Tests for CLI error handling utilities."""

from __future__ import annotations

import pytest

from cli._errors import handle_error, validate_uuid


def test_handle_error_valueerror_reraises() -> None:
    """handle_error re-raises ValueError (not caught by handler)."""
    exc = ValueError("badly formed hexadecimal UUID string")
    with pytest.raises(ValueError, match="badly formed"):
        handle_error(exc)


def test_validate_uuid_valid() -> None:
    """validate_uuid returns None for a valid UUID."""
    result = validate_uuid("550e8400-e29b-41d4-a716-446655440000", "test_id")
    assert result is None


def test_validate_uuid_invalid() -> None:
    """validate_uuid returns 2 for an invalid UUID."""
    result = validate_uuid("not-a-uuid", "test_id")
    assert result == 2


def test_validate_uuid_empty() -> None:
    """validate_uuid returns 2 for an empty string (not a valid UUID)."""
    result = validate_uuid("", "test_id")
    assert result == 2

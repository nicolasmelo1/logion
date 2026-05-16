"""Tests for CLI error handling utilities."""

from __future__ import annotations

from cli._errors import handle_error


def test_handle_error_valueerror() -> None:
    """handle_error catches ValueError and returns exit code 2."""
    exc = ValueError("badly formed hexadecimal UUID string")
    code = handle_error(exc)
    assert code == 2

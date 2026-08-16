# SPDX-License-Identifier: MIT
"""Lazy GitHub device-flow error mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cli._errors import emit_error_json, handle_error

if TYPE_CHECKING:
    # Annotation only. Importing the SDK at module scope would load
    # it during parser setup, which test_cli_startup forbids.
    from logion import APIError


def _detail_text(detail: str | list[dict[str, object]]) -> str:
    if isinstance(detail, list):
        return "; ".join(str(item) for item in detail)
    return str(detail)


def _api_error_code(exc: APIError) -> str:
    detail_text = _detail_text(exc.detail).lower()
    if exc.status_code == 401:
        return "auth_missing"
    if "github_oauth_unconfigured" in detail_text or exc.status_code == 503:
        return "github_oauth_unconfigured"
    if "github_identity_conflict" in detail_text or exc.status_code == 409:
        return "github_identity_conflict"
    if exc.status_code == 404:
        return "not_found"
    if exc.status_code == 422:
        return "validation_failed"
    return "server_error"


def _handle_api_error(exc: APIError, json_output: bool) -> int:
    if json_output:
        emit_error_json(_api_error_code(exc), _detail_text(exc.detail), 1)
        return 1
    return handle_error(exc)


def handle_github_exception(exc: Exception, json_output: bool) -> int:
    """Map SDK errors without importing the SDK during parser setup."""
    from logion import APIError

    if isinstance(exc, APIError):
        return _handle_api_error(exc, json_output)
    return handle_error(exc)

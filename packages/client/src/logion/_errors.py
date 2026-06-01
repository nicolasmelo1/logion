# SPDX-License-Identifier: MIT
"""Error hierarchy for the Logion SDK."""

from __future__ import annotations


class LogionError(Exception):
    """Base exception for all SDK errors."""


class APIError(LogionError):
    """Error returned by the Logion API."""

    def __init__(
        self,
        status_code: int,
        detail: str | list[dict[str, object]],
        request_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.request_id = request_id
        msg = f"{status_code}"
        if request_id:
            msg += f" (request_id={request_id})"
        msg += f": {detail}"
        super().__init__(msg)


class ClientError(APIError):
    """4xx response that isn't mapped to a specific error class."""


class AuthenticationError(APIError):
    """401 — Invalid or missing API key."""


class ForbiddenError(APIError):
    """403 — Insufficient permissions."""


class NotFoundError(APIError):
    """404 — Resource not found."""


class ConflictError(APIError):
    """409 — Resource already exists."""


class ValidationError(APIError):
    """422 — Request body or parameters invalid."""


class RateLimitError(APIError):
    """429 — Too many requests."""


class ServerError(APIError):
    """5xx — Server-side error."""


class TransportError(LogionError):
    """Network-level failure (DNS, connection, timeout, etc.).

    Wraps an ``httpx.TransportError`` after retries are exhausted.
    """

    def __init__(
        self,
        message: str,
        original: Exception | None = None,
    ) -> None:
        self.original = original
        super().__init__(message)

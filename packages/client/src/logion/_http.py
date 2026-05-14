"""HTTP transport wrapper with retry and auth."""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from logion._config import ClientConfig
from logion._errors import (
    APIError,
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)

_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
_RETRYABLE_METHODS = {"GET", "HEAD", "OPTIONS"}
_STATUS_ERROR_MAP: dict[int, type[APIError]] = {
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}


def _raise_for_status(response: httpx.Response) -> None:
    """Raise a typed SDK error for non-2xx responses."""
    if response.is_success:
        return

    status_code = response.status_code
    detail: str | list[dict[str, object]] = response.text
    request_id: str | None = response.headers.get("x-request-id")

    try:
        body = response.json()
        detail = body.get("detail", detail)
    except Exception:
        pass

    error_cls = _STATUS_ERROR_MAP.get(status_code, ServerError)

    raise error_cls(
        status_code=status_code,
        detail=detail,
        request_id=request_id,
    )


class HttpClient:
    """Wraps httpx.Client with retry, auth, and error mapping."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout,
            headers=self._build_headers(config),
        )

    @staticmethod
    def _build_headers(config: ClientConfig) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
            **config.extra_headers,
        }
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a request with automatic retry and error mapping.

        Only idempotent methods (GET, HEAD, OPTIONS) are retried on
        transient failures to avoid duplicating side-effects.
        """
        can_retry = method.upper() in _RETRYABLE_METHODS
        last_exc: Exception | None = None
        max_attempts = self._config.max_retries + 1 if can_retry else 1

        for attempt in range(max_attempts):
            request_id = str(uuid.uuid4())
            headers = {"X-Request-ID": request_id}

            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    headers=headers,
                )
            except httpx.TransportError as exc:
                last_exc = exc
                if can_retry and attempt < max_attempts - 1:
                    backoff = 0.5 * (2**attempt)
                    time.sleep(backoff)
                    continue
                raise

            if (
                response.status_code in _RETRYABLE_STATUS_CODES
                and can_retry
                and attempt < max_attempts - 1
            ):
                backoff = 0.5 * (2**attempt)
                time.sleep(backoff)
                continue

            _raise_for_status(response)
            return response.json()

        assert last_exc is not None  # for type checker
        raise last_exc

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()

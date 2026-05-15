"""HTTP transport wrapper with retry and auth."""

from __future__ import annotations

import time
import uuid
from typing import Any, TypeVar, cast

import httpx
from pydantic import BaseModel

from logion._config import ClientConfig
from logion._errors import (
    APIError,
    AuthenticationError,
    ClientError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TransportError,
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

T = TypeVar("T", bound=BaseModel)


def _raise_for_status(response: httpx.Response) -> None:
    """Raise a typed SDK error for non-2xx responses."""
    if response.is_success:
        return

    status_code = response.status_code
    request_id: str | None = response.headers.get("x-request-id")
    detail: str | list[dict[str, object]] = response.text

    try:
        body = response.json()
        detail = body.get("detail", detail)
    except Exception:  # nosec B110 — intentional: non-JSON responses are fine as plain text
        pass

    error_cls = _STATUS_ERROR_MAP.get(status_code)
    if error_cls is None:
        error_cls = ServerError if status_code >= 500 else ClientError

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
        """Send a request and return raw JSON dict."""
        if self._config.max_retries < 0:
            msg = f"max_retries must be >= 0, got {self._config.max_retries}"
            raise ValueError(msg)
        can_retry = method.upper() in _RETRYABLE_METHODS
        last_exc: httpx.TransportError | None = None
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
                raise TransportError(
                    f"Request failed after {attempt + 1} attempt(s): {exc}",
                    original=exc,
                ) from exc

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
        raise TransportError(
            f"Request failed after {max_attempts} attempts",
            original=last_exc,
        ) from last_exc

    def request_model(
        self,
        method: str,
        path: str,
        model_type: type[T],
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> T:
        """Send a request and parse the response into a Pydantic model."""
        data = self.request(
            method,
            path,
            params=params,
            json=json,
        )
        return cast(T, model_type.model_validate(data))

    def request_list(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Send a request and return raw JSON as a list of dicts.

        Use this for endpoints whose OpenAPI contract defines an array
        response (``[...]``) rather than a JSON object.
        """
        data = self.request(method, path, params=params, json=json)
        if not isinstance(data, list):
            msg = (
                f"Expected a JSON array from "
                f"{method} {path}, got {type(data).__name__}"
            )
            raise TypeError(msg)
        return data

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()

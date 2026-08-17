# SPDX-License-Identifier: MIT
"""HTTP transport wrapper with retry and auth."""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping, Sequence
from typing import TypeVar, cast
from uuid import UUID

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
from logion._json import JsonObject, JsonValue

#: Values httpx accepts in a query string. Nested structures are not
#: representable in a URL, so this is deliberately flat -- unlike a
#: JSON body, which may nest freely. A sequence is the one exception:
#: it becomes a repeated ``key=`` pair.
type QueryScalar = str | int | float | bool | UUID | None
type QueryValue = QueryScalar | Sequence[QueryScalar]
type QueryParams = Mapping[str, QueryValue]

type _WireScalar = str | int | float | bool
type _WireValue = _WireScalar | Sequence[_WireScalar]


def _encode_scalar(value: QueryScalar) -> _WireScalar | None:
    """Render one query value, or ``None`` to drop it."""
    if value is None:
        return None
    return str(value) if isinstance(value, UUID) else value


def _encode_params(params: QueryParams | None) -> dict[str, _WireValue] | None:
    """Render query values as something httpx will accept.

    httpx stringifies primitives itself but its signature does not admit
    a ``UUID``, and several operations take ``str | UUID`` ids. Encoding
    here keeps that conversion in one visible place instead of relying
    on httpx's ``str()`` fallback. ``None`` values are dropped: an unset
    optional parameter should not appear in the query string, and that
    applies inside a repeated-parameter sequence too.
    """
    if params is None:
        return None
    encoded: dict[str, _WireValue] = {}
    for key, value in params.items():
        if isinstance(value, str | int | float | bool | UUID):
            scalar = _encode_scalar(value)
            if scalar is not None:
                encoded[key] = scalar
        elif value is not None:
            items = [_encode_scalar(item) for item in value]
            encoded[key] = [item for item in items if item is not None]
    return encoded


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
    detail: str | list[JsonObject] = response.text

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
        params: QueryParams | None = None,
        json: JsonObject | None = None,
    ) -> JsonValue:
        """Send a request and return JSON when available, text otherwise.

        The return type is the full JSON grammar, not just an object:
        array-valued endpoints exist (see :meth:`request_list`), a
        non-JSON body falls back to its text, and an empty body
        becomes ``{}``. Callers narrow before use.
        """
        if self._config.max_retries < 0:
            msg = f"max_retries must be >= 0, got {self._config.max_retries}"
            raise ValueError(msg)
        can_retry = method.upper() in _RETRYABLE_METHODS
        wire_params = _encode_params(params)
        last_exc: httpx.TransportError | None = None
        max_attempts = self._config.max_retries + 1 if can_retry else 1

        for attempt in range(max_attempts):
            request_id = str(uuid.uuid4())
            headers = {"X-Request-ID": request_id}

            try:
                response = self._client.request(
                    method,
                    path,
                    params=wire_params,
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
            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError:
                return response.text

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
        params: QueryParams | None = None,
        json: JsonObject | None = None,
    ) -> T:
        """Send a request and parse the response into a Pydantic model."""
        data = self.request(
            method,
            path,
            params=params,
            json=json,
        )
        return cast(T, model_type.model_validate(data))

    def request_object(
        self,
        method: str,
        path: str,
        *,
        params: QueryParams | None = None,
        json: JsonObject | None = None,
    ) -> JsonObject:
        """Send a request and return the response as a JSON object.

        Use this for endpoints with no generated model whose contract
        still guarantees an object response.
        """
        data = self.request(method, path, params=params, json=json)
        return _as_object(data, method, path)

    def request_list(
        self,
        method: str,
        path: str,
        *,
        params: QueryParams | None = None,
        json: JsonObject | None = None,
    ) -> list[JsonObject]:
        """Send a request and return raw JSON as a list of dicts.

        Use this for endpoints whose OpenAPI contract defines an array
        response (``[...]``) rather than a JSON object.
        """
        data = self.request(method, path, params=params, json=json)
        return _as_object_list(data, method, path)

    def request_items(
        self,
        method: str,
        path: str,
        *,
        params: QueryParams | None = None,
        json: JsonObject | None = None,
    ) -> list[JsonObject]:
        """Send a request and return its collection of objects.

        Tolerates both collection encodings the API uses: a bare array,
        and an object wrapping the array under ``items``.
        """
        data = self.request(method, path, params=params, json=json)
        if isinstance(data, dict):
            data = data.get("items")
        return _as_object_list(data, method, path)

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()


def _as_object(data: JsonValue, method: str, path: str) -> JsonObject:
    """Narrow a response body to a JSON object, or raise."""
    if not isinstance(data, dict):
        msg = (
            f"Expected a JSON object from "
            f"{method} {path}, got {type(data).__name__}"
        )
        raise TypeError(msg)
    return data


def _as_object_list(
    data: JsonValue, method: str, path: str
) -> list[JsonObject]:
    """Narrow a response body to a list of JSON objects, or raise."""
    if not isinstance(data, list):
        msg = (
            f"Expected a JSON array from "
            f"{method} {path}, got {type(data).__name__}"
        )
        raise TypeError(msg)
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            msg = (
                f"Expected a JSON object at index {index} of the array "
                f"from {method} {path}, got {type(item).__name__}"
            )
            raise TypeError(msg)
    return [item for item in data if isinstance(item, dict)]

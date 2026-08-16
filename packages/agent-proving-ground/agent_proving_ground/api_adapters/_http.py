from __future__ import annotations

import json
import urllib.error
import urllib.request

from agent_proving_ground._json import JsonObject, JsonValue
from agent_proving_ground.config import InconclusiveRun


class HealthCheckError(InconclusiveRun):
    """Raised when an API adapter cannot reach the configured endpoint."""


def _http_get_json_sync(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    headers: dict[str, str] | None = None,
) -> JsonObject:
    """Fetch JSON from a URL using stdlib urllib.

    Raises HealthCheckError on network or HTTP failures so adapters can
    classify the run as inconclusive rather than a product failure.
    """
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", **(headers or {})},
        method="GET",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=timeout_seconds
        ) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise HealthCheckError(
            f"health check failed: HTTP {exc.code} at {url}"
        ) from exc
    except urllib.error.URLError as exc:
        raise HealthCheckError(
            f"health check failed: cannot reach {url}: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise HealthCheckError(
            f"health check timed out after {timeout_seconds}s at {url}"
        ) from exc
    try:
        data: JsonObject = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HealthCheckError(
            f"health check returned non-JSON from {url}: {exc}"
        ) from exc
    return data


async def http_get_json(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    headers: dict[str, str] | None = None,
) -> JsonObject:
    """Async wrapper around :func:`_http_get_json_sync`."""
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _http_get_json_sync(
            url, timeout_seconds=timeout_seconds, headers=headers
        ),
    )


def _http_request_json_sync(
    method: str,
    url: str,
    *,
    timeout_seconds: float = 15.0,
    headers: dict[str, str] | None = None,
    body: JsonObject | None = None,
) -> tuple[int, JsonValue]:
    """Perform an HTTP request and return ``(status, parsed_json)``.

    Unlike the health-check helper, HTTP error statuses are returned to
    the caller instead of raised, so query code can treat 404 as "not
    found" evidence rather than an inconclusive run.
    """
    data = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, headers=request_headers, method=method, data=data
    )
    try:
        with urllib.request.urlopen(
            request, timeout=timeout_seconds
        ) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
    except urllib.error.URLError as exc:
        raise HealthCheckError(
            f"request failed: cannot reach {url}: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise HealthCheckError(
            f"request timed out after {timeout_seconds}s at {url}"
        ) from exc
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else None
    except json.JSONDecodeError:
        parsed = None
    return status, parsed


async def http_request_json(
    method: str,
    url: str,
    *,
    timeout_seconds: float = 15.0,
    headers: dict[str, str] | None = None,
    body: JsonObject | None = None,
) -> tuple[int, JsonValue]:
    """Async wrapper around :func:`_http_request_json_sync`."""
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _http_request_json_sync(
            method,
            url,
            timeout_seconds=timeout_seconds,
            headers=headers,
            body=body,
        ),
    )


async def health_check_endpoint(base_url: str, path: str = "/health") -> None:
    """Verify that base_url + path returns a successful JSON response.

    The endpoint must complete without network/timeout errors and respond
    with HTTP 200 and a JSON object body. Any other HTTP status (including
    3xx/4xx/5xx) or non-JSON body raises HealthCheckError so the run can
    be classified as inconclusive.
    """
    url = base_url.rstrip("/") + path
    data = await http_get_json(url)
    if not isinstance(data, dict):
        raise HealthCheckError(
            f"health check returned non-object JSON from {url}"
        )

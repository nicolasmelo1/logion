from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from logion_agent_proving_ground.config import InconclusiveRun


class HealthCheckError(InconclusiveRun):
    """Raised when an API adapter cannot reach the configured endpoint."""


def _http_get_json_sync(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
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
        data: dict[str, Any] = json.loads(body.decode("utf-8"))
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
) -> dict[str, Any]:
    """Async wrapper around :func:`_http_get_json_sync`."""
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _http_get_json_sync(
            url, timeout_seconds=timeout_seconds, headers=headers
        ),
    )


async def health_check_endpoint(
    base_url: str, path: str = "/v1/health"
) -> None:
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

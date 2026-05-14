"""Health check resource."""

from __future__ import annotations

from typing import Any

from logion._http import HttpClient


class HealthResource:
    """Access health check endpoints."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def check(self) -> dict[str, Any]:
        """Check if the API is healthy.

        The health endpoint returns a free-form dict
        (e.g. ``{"status": "ok"}``) — no generated model exists.
        """
        return self._http.request("GET", "/health")

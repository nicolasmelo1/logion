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

        Returns:
            Health status dict, e.g. {"status": "ok"}.
        """
        return self._http.request("GET", "/health")

# SPDX-License-Identifier: MIT
"""Runner operator resource."""

from __future__ import annotations

from logion._http import HttpClient
from logion._json import JsonObject


class RunnersResource:
    """Provision credentials for reference runners."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def enroll(self, name: str) -> JsonObject:
        """Enroll one runner and return its one-time credentials."""
        name = name.strip()
        if not name:
            raise ValueError("runner name must not be empty")
        return self._http.request_object(
            "POST", "/v1/runners/enroll", json={"name": name}
        )

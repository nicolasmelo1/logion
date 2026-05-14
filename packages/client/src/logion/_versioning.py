"""Versioned namespace factory."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1 import V1Namespace


class VersionedNamespaces:
    """Lazy namespace accessors for each API version."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._v1: V1Namespace | None = None

    @property
    def v1(self) -> V1Namespace:
        """Access the v1 API namespace."""
        if self._v1 is None:
            self._v1 = V1Namespace(self._http)
        return self._v1

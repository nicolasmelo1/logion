"""Logion client — entry point for the SDK."""

from __future__ import annotations

from logion._config import ClientConfig
from logion._http import HttpClient
from logion._versioning import VersionedNamespaces


class LogionClient:
    """Python client for the Logion API.

    Usage::

        from logion import LogionClient

        client = LogionClient(api_key="lgk_...")
        client.v1.health.check()
        client.v1.listings.search(query="rag")
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "https://api.logion.dev",
        timeout: float = 30.0,
        max_retries: int = 3,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        config = ClientConfig(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            extra_headers=extra_headers or {},
        )
        self._http = HttpClient(config)
        self._namespaces = VersionedNamespaces(self._http)

    @property
    def v1(self):
        """Access the v1 API namespace."""
        return self._namespaces.v1

    def close(self) -> None:
        """Close the underlying HTTP connection."""
        self._http.close()

    def __enter__(self) -> LogionClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

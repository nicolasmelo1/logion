"""Logion client — entry point for the SDK."""

from __future__ import annotations

from logion._config import DEFAULT_BASE_URL, ClientConfig
from logion._http import HttpClient
from logion._versioning import VersionedNamespaces


class LogionClient:
    """Python client for the Logion API.

    Configuration can be provided via constructor arguments or
    environment variables (``LOGION_API_KEY``, ``LOGION_BASE_URL``).

    Usage::

        from logion import LogionClient

        client = LogionClient(api_key="lgk_...")
        client.v1.health.check()
        client.v1.listings.search(query="rag")
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        config = ClientConfig(
            base_url=base_url or DEFAULT_BASE_URL,
            api_key=api_key or "",
            timeout=timeout if timeout is not None else 30.0,
            max_retries=(max_retries if max_retries is not None else 3),
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

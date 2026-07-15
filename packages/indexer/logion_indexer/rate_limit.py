"""Per-host rate limiter (default 1 req/s)."""

from __future__ import annotations

import time
from urllib.parse import urlparse


class RateLimiter:
    """Enforce a minimum interval between requests to the same host.

    Thread-unsafe by design — the indexer is single-threaded per host.
    """

    def __init__(self, default_rps: float = 1.0) -> None:
        self._default_interval = 1.0 / default_rps if default_rps > 0 else 0.0
        self._per_host: dict[str, float] = {}
        self._overrides: dict[str, float] = {}

    def set_rps(self, host: str, rps: float) -> None:
        interval = 1.0 / rps if rps > 0 else 0.0
        self._overrides[host] = interval

    def wait(self, url: str) -> None:
        """Block until the per-host interval has elapsed."""
        host = urlparse(url).hostname or url
        interval = self._overrides.get(host, self._default_interval)
        now = time.monotonic()
        last = self._per_host.get(host, 0.0)
        elapsed = now - last
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._per_host[host] = time.monotonic()

    def reset(self) -> None:
        self._per_host.clear()

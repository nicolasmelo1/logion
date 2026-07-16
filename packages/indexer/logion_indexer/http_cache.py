"""On-disk HTTP cache for conditional GETs (ETag / Last-Modified).

Stores each cached response as two files under the cache directory: a
``<key>.json`` metadata sidecar (status, headers, ``ETag``,
``Last-Modified``) and a ``<key>.body`` payload.  The key is the SHA-256
of the URL so arbitrary URLs map to filesystem-safe names.

The :class:`Transport` layer uses this to send ``If-None-Match`` /
``If-Modified-Since`` headers and serve the stored body on ``304 Not
Modified``.  The in-memory cache on :class:`Transport` is retained for
within-run dedupe; this disk layer persists across runs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CacheEntry:
    """A cached HTTP response with its validators."""

    status: int
    body: bytes
    headers: dict[str, str]
    etag: str = ""
    last_modified: str = ""


def default_cache_dir() -> Path:
    """Return the default cache directory under ``~/.cache``."""
    return Path.home() / ".cache" / "logion-indexer"


class DiskCache:
    """A tiny on-disk cache keyed by URL, for conditional requests."""

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _meta_path(self, url: str) -> Path:
        return self.cache_dir / f"{self._key(url)}.json"

    def _body_path(self, url: str) -> Path:
        return self.cache_dir / f"{self._key(url)}.body"

    def get(self, url: str) -> CacheEntry | None:
        """Return the cached entry for *url*, or ``None`` when absent."""
        meta_path = self._meta_path(url)
        body_path = self._body_path(url)
        if not meta_path.is_file() or not body_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text())
            body = body_path.read_bytes()
        except (OSError, ValueError):
            return None
        if not isinstance(meta, dict):
            return None
        headers = meta.get("headers") or {}
        if not isinstance(headers, dict):
            headers = {}
        return CacheEntry(
            status=int(meta.get("status", 200)),
            body=body,
            headers={str(k): str(v) for k, v in headers.items()},
            etag=str(meta.get("etag", "")),
            last_modified=str(meta.get("last_modified", "")),
        )

    def store(
        self,
        url: str,
        status: int,
        body: bytes,
        headers: dict[str, str],
    ) -> None:
        """Persist a response with its ``ETag`` / ``Last-Modified``.

        No-op when the response carries neither validator, since a
        conditional request would be impossible to issue later.
        """
        etag, last_modified = _validators(headers)
        if not etag and not last_modified:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._body_path(url).write_bytes(body)
            self._meta_path(url).write_text(
                json.dumps({
                    "url": url,
                    "status": status,
                    "headers": headers,
                    "etag": etag,
                    "last_modified": last_modified,
                })
            )
        except OSError:
            # A best-effort cache: a write failure must never break a run.
            return


def _validators(headers: dict[str, str]) -> tuple[str, str]:
    """Extract ``ETag`` and ``Last-Modified`` (case-insensitively)."""
    etag = ""
    last_modified = ""
    for key, value in headers.items():
        low = key.lower()
        if low == "etag":
            etag = value
        elif low == "last-modified":
            last_modified = value
    return etag, last_modified

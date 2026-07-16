"""Tests for on-disk conditional-request caching (ETag/Last-Modified)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from logion_indexer.http_cache import DiskCache
from logion_indexer.transport import HttpResponse, Transport

URL = "https://example.com/data.json"


class _ConditionalTransport(Transport):
    """Transport whose network seam simulates a validating origin.

    Serves the body with an ``ETag`` on the first request, then ``304``
    whenever a conditional header is present.  Records the headers of
    each raw request for assertions.
    """

    def __init__(self, *, cache_dir: str) -> None:
        super().__init__(cache_dir=cache_dir)
        self.seen_headers: list[dict[str, str]] = []

    def _raw_get(
        self,
        url: str,  # noqa: ARG002
        headers: Mapping[str, str],
    ) -> HttpResponse:
        self.seen_headers.append(dict(headers))
        if "If-None-Match" in headers or "If-Modified-Since" in headers:
            return HttpResponse(304, b"", {"ETag": '"v1"'})
        return HttpResponse(200, b'{"hello":"world"}', {"ETag": '"v1"'})


class TestDiskCache:
    def test_store_requires_validator(self, tmp_path: Path) -> None:
        cache = DiskCache(tmp_path)
        cache.store(URL, 200, b"body", {})  # no ETag/Last-Modified
        assert cache.get(URL) is None

    def test_roundtrip(self, tmp_path: Path) -> None:
        cache = DiskCache(tmp_path)
        cache.store(URL, 200, b"body", {"ETag": '"abc"'})
        entry = cache.get(URL)
        assert entry is not None
        assert entry.body == b"body"
        assert entry.etag == '"abc"'


class TestConditionalGet:
    def test_304_served_from_disk(self, tmp_path: Path) -> None:
        # First run: populates the disk cache with the body + ETag.
        t1 = _ConditionalTransport(cache_dir=str(tmp_path))
        r1 = t1.get(URL)
        assert r1.status == 200
        assert r1.body == b'{"hello":"world"}'
        assert "If-None-Match" not in t1.seen_headers[0]

        # Second run (fresh in-memory state, shared disk): conditional
        # request → 304 → cached body served as 200.
        t2 = _ConditionalTransport(cache_dir=str(tmp_path))
        r2 = t2.get(URL)
        assert r2.status == 200
        assert r2.body == b'{"hello":"world"}'
        assert t2.seen_headers[0].get("If-None-Match") == '"v1"'

    def test_no_cache_dir_no_conditional(self, tmp_path: Path) -> None:  # noqa: ARG002
        t = _ConditionalTransport.__new__(_ConditionalTransport)
        Transport.__init__(t)  # no cache_dir
        t.seen_headers = []
        resp = t.get(URL)
        assert resp.status == 200
        assert "If-None-Match" not in t.seen_headers[0]

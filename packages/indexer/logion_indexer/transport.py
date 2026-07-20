"""Transport layer: all HTTP goes through here so tests can fake it."""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from http.client import RemoteDisconnected
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from .http_cache import DiskCache

if TYPE_CHECKING:
    from collections.abc import Mapping

GET_TIMEOUT_SECONDS = 30
GET_MAX_ATTEMPTS = 3
GET_RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass
class HttpResponse:
    """A simple HTTP response wrapper."""

    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> object:
        return json.loads(self.body.decode("utf-8"))

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class Transport:
    """HTTP transport with caching, rate limiting, and robots.txt.

    All network access in the indexer goes through this class so tests
    can substitute a fake transport.
    """

    def __init__(
        self,
        *,
        user_agent: str = "logion-indexer/0.1 (+https://logion.sh)",
        github_token: str | None = None,
        api_key: str | None = None,
        cache_dir: str | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.github_token = github_token
        self.api_key = api_key
        self.api_base_host = urlparse(
            "https://api.logion.sh"
        ).hostname  # default API host
        self._cache: dict[str, tuple[int, bytes, dict[str, str]]] = {}
        self._call_log: list[str] = []
        self._disk_cache = DiskCache(cache_dir) if cache_dir else None

    def set_api_base_url(self, base_url: str) -> None:
        """Update the expected API host so API keys are only sent there."""
        self.api_base_host = urlparse(base_url).hostname or ""

    @staticmethod
    def _is_github_host(url: str) -> bool:
        """True if the URL hostname is github.com or api.github.com."""
        host = (urlparse(url).hostname or "").lower()
        return host in ("github.com", "api.github.com")

    def _is_api_host(self, url: str) -> bool:
        """True if the URL's hostname matches the configured API host."""
        host = (urlparse(url).hostname or "").lower()
        api_host = self.api_base_host or ""
        return bool(api_host) and host == api_host.lower()

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        use_cache: bool = True,
    ) -> HttpResponse:
        """Perform an HTTP GET, with in-memory and on-disk caching.

        When ``use_cache`` is True, successful responses are stored in
        an in-memory dict keyed by URL and returned on subsequent calls
        within the same run without hitting the network.  When a disk
        cache is configured, a stored ``ETag`` / ``Last-Modified`` is
        sent as ``If-None-Match`` / ``If-Modified-Since``; a ``304 Not
        Modified`` serves the cached body.
        """
        self._call_log.append(f"GET {url}")
        h = {"User-Agent": self.user_agent}
        if headers:
            h.update(dict(headers))
        if self.github_token and self._is_github_host(url):
            h["Authorization"] = f"Bearer {self.github_token}"
        if self.api_key and self._is_api_host(url):
            h["Authorization"] = f"Bearer {self.api_key}"

        if use_cache and url in self._cache:
            status, body, resp_headers = self._cache[url]
            return HttpResponse(status, body, resp_headers)

        entry = (
            self._disk_cache.get(url)
            if use_cache and self._disk_cache
            else None
        )
        if entry is not None:
            if entry.etag:
                h["If-None-Match"] = entry.etag
            if entry.last_modified:
                h["If-Modified-Since"] = entry.last_modified

        resp = self._raw_get(url, h)

        if resp.status == 304 and entry is not None:
            resp = HttpResponse(200, entry.body, entry.headers)
        elif resp.status == 200 and use_cache and self._disk_cache is not None:
            self._disk_cache.store(url, resp.status, resp.body, resp.headers)

        if use_cache and resp.status == 200:
            self._cache[url] = (resp.status, resp.body, resp.headers)
        return resp

    def _raw_get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        """Perform GET with bounded retries for transient failures."""
        req = urllib.request.Request(url, headers=dict(headers), method="GET")
        for attempt in range(GET_MAX_ATTEMPTS):
            try:
                with urllib.request.urlopen(
                    req, timeout=GET_TIMEOUT_SECONDS
                ) as resp:
                    data = resp.read()
                    return HttpResponse(resp.status, data, dict(resp.headers))
            except HTTPError as exc:
                should_retry = (
                    exc.code in GET_RETRY_STATUSES
                    and attempt + 1 < GET_MAX_ATTEMPTS
                )
                if should_retry:
                    exc.close()
                else:
                    try:
                        return HttpResponse(
                            exc.code,
                            exc.read(),
                            dict(exc.headers or {}),
                        )
                    finally:
                        exc.close()
            except (RemoteDisconnected, URLError, TimeoutError):
                if attempt + 1 == GET_MAX_ATTEMPTS:
                    raise
            time.sleep(2**attempt)
        raise AssertionError("unreachable")

    def post(
        self,
        url: str,
        *,
        json_body: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Perform an HTTP POST."""
        self._call_log.append(f"POST {url}")
        h = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
        }
        if headers:
            h.update(dict(headers))
        if self.api_key and self._is_api_host(url):
            h["Authorization"] = f"Bearer {self.api_key}"

        data = b""
        if json_body is not None:
            data = json.dumps(dict(json_body)).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        try:
            with urllib.request.urlopen(
                req, timeout=GET_TIMEOUT_SECONDS
            ) as resp:
                body = resp.read()
                return HttpResponse(resp.status, body, dict(resp.headers))
        except HTTPError as e:
            return HttpResponse(e.code, e.read())

    def patch(
        self,
        url: str,
        *,
        json_body: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Perform an HTTP PATCH."""
        self._call_log.append(f"PATCH {url}")
        h = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
        }
        if headers:
            h.update(dict(headers))
        if self.api_key and self._is_api_host(url):
            h["Authorization"] = f"Bearer {self.api_key}"

        data = b""
        if json_body is not None:
            data = json.dumps(dict(json_body)).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=h, method="PATCH")
        try:
            with urllib.request.urlopen(
                req, timeout=GET_TIMEOUT_SECONDS
            ) as resp:
                body = resp.read()
                return HttpResponse(resp.status, body, dict(resp.headers))
        except HTTPError as e:
            return HttpResponse(e.code, e.read())

    def put(
        self,
        url: str,
        *,
        body: bytes,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Perform a raw HTTP PUT (for presigned uploads)."""
        self._call_log.append(f"PUT {url}")
        h = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/octet-stream",
        }
        if headers:
            h.update(dict(headers))

        req = urllib.request.Request(url, data=body, headers=h, method="PUT")
        try:
            with urllib.request.urlopen(
                req, timeout=GET_TIMEOUT_SECONDS
            ) as resp:
                resp_body = resp.read()
                return HttpResponse(resp.status, resp_body, dict(resp.headers))
        except HTTPError as e:
            return HttpResponse(e.code, e.read())

    @property
    def call_log(self) -> list[str]:
        """List of HTTP method+URL strings (for test assertions)."""
        return self._call_log


class FakeTransport(Transport):
    """In-memory transport for tests.  Never touches the network."""

    def __init__(
        self,
        *,
        github_token: str | None = None,
        api_key: str | None = None,
    ) -> None:
        super().__init__(github_token=github_token, api_key=api_key)
        self._responses: dict[str, HttpResponse] = {}
        self._post_responses: dict[str, HttpResponse] = {}
        self._patch_responses: dict[str, HttpResponse] = {}
        self._put_responses: dict[str, HttpResponse] = {}

    def set_response(self, url: str, response: HttpResponse) -> None:
        self._responses[url] = response

    def set_post_response(self, url: str, response: HttpResponse) -> None:
        self._post_responses[url] = response

    def set_patch_response(self, url: str, response: HttpResponse) -> None:
        self._patch_responses[url] = response

    def set_put_response(self, url: str, response: HttpResponse) -> None:
        self._put_responses[url] = response

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,  # noqa: ARG002
        use_cache: bool = True,  # noqa: ARG002
    ) -> HttpResponse:
        self._call_log.append(f"GET {url}")
        if url in self._responses:
            return self._responses[url]
        return HttpResponse(404, b'{"error":"not found"}')

    def post(
        self,
        url: str,
        *,
        json_body: Mapping[str, object] | None = None,  # noqa: ARG002
        headers: Mapping[str, str] | None = None,  # noqa: ARG002
    ) -> HttpResponse:
        self._call_log.append(f"POST {url}")
        if url in self._post_responses:
            return self._post_responses[url]
        return HttpResponse(404, b'{"error":"not found"}')

    def patch(
        self,
        url: str,
        *,
        json_body: Mapping[str, object] | None = None,  # noqa: ARG002
        headers: Mapping[str, str] | None = None,  # noqa: ARG002
    ) -> HttpResponse:
        self._call_log.append(f"PATCH {url}")
        if url in self._patch_responses:
            return self._patch_responses[url]
        return HttpResponse(404, b'{"error":"not found"}')

    def put(
        self,
        url: str,
        *,
        body: bytes,  # noqa: ARG002
        headers: Mapping[str, str] | None = None,  # noqa: ARG002
    ) -> HttpResponse:
        self._call_log.append(f"PUT {url}")
        if url in self._put_responses:
            return self._put_responses[url]
        return HttpResponse(404, b'{"error":"not found"}')

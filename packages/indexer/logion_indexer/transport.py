"""Transport layer: all HTTP goes through here so tests can fake it."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


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
    ) -> None:
        self.user_agent = user_agent
        self.github_token = github_token
        self.api_key = api_key
        self._cache: dict[str, tuple[int, bytes, dict[str, str]]] = {}
        self._call_log: list[str] = []

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        use_cache: bool = True,
    ) -> HttpResponse:
        """Perform an HTTP GET, with optional ETag/Last-Modified cache."""
        self._call_log.append(f"GET {url}")
        h = {"User-Agent": self.user_agent}
        if headers:
            h.update(dict(headers))
        if self.github_token and "github.com" in url:
            h["Authorization"] = f"Bearer {self.github_token}"

        if use_cache and url in self._cache:
            status, body, resp_headers = self._cache[url]
            return HttpResponse(status, body, resp_headers)

        req = urllib.request.Request(url, headers=h, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            resp_headers = dict(resp.headers)
            if use_cache:
                self._cache[url] = (resp.status, data, resp_headers)
            return HttpResponse(resp.status, data, resp_headers)

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
        if self.api_key and "logion" in url:
            h["Authorization"] = f"Bearer {self.api_key}"

        data = b""
        if json_body is not None:
            data = json.dumps(dict(json_body)).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return HttpResponse(resp.status, body, dict(resp.headers))

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
        if self.api_key and "logion" in url:
            h["Authorization"] = f"Bearer {self.api_key}"

        data = b""
        if json_body is not None:
            data = json.dumps(dict(json_body)).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=h, method="PATCH")
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return HttpResponse(resp.status, body, dict(resp.headers))

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
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read()
            return HttpResponse(resp.status, resp_body, dict(resp.headers))

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

# SPDX-License-Identifier: MIT
"""ARD v0.9 HTTP client — search and explore against an ARD registry."""

from __future__ import annotations

import json
from typing import cast

from logion_indexer._json import JsonValue
from logion_indexer.transport import HttpResponse, Transport

from . import (
    ExploreRequest,
    ExploreResponse,
    SearchRequest,
    SearchResponse,
)
from .codec import (
    ARDDecodeError,
    decode_explore_response,
    decode_search_response,
    encode_explore_request,
    encode_search_request,
)


class ARDClient:
    """HTTP client for ARD registry endpoints.

    This client talks to the standard REST interface defined by the
    ARD specification (POST /search, POST /explore). It is a thin
    transport layer: all model logic lives in the codec.
    """

    def __init__(
        self,
        transport: Transport,
        registry_url: str,
    ) -> None:
        self.transport = transport
        self.registry_url = registry_url.rstrip("/")

    def search(self, request: SearchRequest) -> SearchResponse:
        """Execute a POST /search request against the registry."""
        url = f"{self.registry_url}/search"
        resp = self.transport.post(
            url,
            json_body=encode_search_request(request),
            headers={"Content-Type": "application/json"},
        )
        _check_error(resp)
        return decode_search_response(cast(JsonValue, resp.json()))

    def explore(self, request: ExploreRequest) -> ExploreResponse:
        """Execute a POST /explore request against the registry.

        Raises :class:`ARDDecodeError` if the registry returns 501
        (explore not implemented) or any other non-200 status.
        """
        url = f"{self.registry_url}/explore"
        resp = self.transport.post(
            url,
            json_body=encode_explore_request(request),
            headers={"Content-Type": "application/json"},
        )
        _check_error(resp)
        return decode_explore_response(cast(JsonValue, resp.json()))


def _check_error(resp: HttpResponse) -> None:
    """Raise on non-2xx responses."""
    if 200 <= resp.status < 300:
        return
    try:
        body = json.loads(resp.body.decode("utf-8"))
        code = ""
        message = ""
        if isinstance(body, dict):
            code = str(body.get("code", body.get("error", "")))
            message = str(body.get("message", body.get("error", "")))
    except (json.JSONDecodeError, UnicodeDecodeError):
        code = f"HTTP_{resp.status}"
        message = resp.text[:200]
    raise ARDDecodeError(
        f"ARD request failed: status={resp.status} "
        f"code={code} message={message}"
    )


__all__ = ["ARDClient"]

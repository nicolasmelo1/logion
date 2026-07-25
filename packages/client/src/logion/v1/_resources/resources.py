# SPDX-License-Identifier: MIT
"""Resources resource — search, get, and versions for generic indexed
resources.
"""

from __future__ import annotations

from logion._http import HttpClient


class ResourcesResource:
    """Search and browse generic indexed resources (skills, plugins, etc.)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def search(
        self,
        *,
        query: str | None = None,
        resource_type: str | None = None,
        tags: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, object]:
        """Search indexed resources.

        Parameters
        ----------
        query:
            Free-text search query.
        resource_type:
            Filter by resource type (``skill``, ``plugin``, ``mcp_server``,
            ``model``, ``course``).
        tags:
            Comma-separated tag filter.
        limit:
            Page size (max 50).
        cursor:
            Pagination cursor from a previous response.
        """
        params: dict[str, object] = {}
        if query is not None:
            params["query"] = query
        if resource_type is not None:
            params["resource_type"] = resource_type
        if tags is not None:
            params["tags"] = tags
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        result = self._http.request(
            "GET",
            "/v1/resources",
            params=params,
        )
        if not isinstance(result, dict):
            msg = (
                f"Expected a JSON object from GET /v1/resources, "
                f"got {type(result).__name__}"
            )
            raise TypeError(msg)
        return result

    def get(
        self,
        *,
        resource_id: str,
    ) -> dict[str, object]:
        """Get detail for a single indexed resource.

        Parameters
        ----------
        resource_id:
            The resource's canonical identifier string (e.g.
            ``skill:gh:owner/repo``).
        """
        result = self._http.request(
            "GET",
            f"/v1/resources/{resource_id}",
        )
        if not isinstance(result, dict):
            msg = (
                f"Expected a JSON object from "
                f"GET /v1/resources/{resource_id}, "
                f"got {type(result).__name__}"
            )
            raise TypeError(msg)
        return result

    def versions(
        self,
        *,
        resource_id: str,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, object]:
        """List available versions of a resource.

        Parameters
        ----------
        resource_id:
            The resource's canonical identifier string.
        limit:
            Page size.
        cursor:
            Pagination cursor from a previous response.
        """
        params: dict[str, object] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        result = self._http.request(
            "GET",
            f"/v1/resources/{resource_id}/versions",
            params=params,
        )
        if not isinstance(result, dict):
            msg = (
                f"Expected a JSON object from "
                f"GET /v1/resources/{resource_id}/versions, "
                f"got {type(result).__name__}"
            )
            raise TypeError(msg)
        return result

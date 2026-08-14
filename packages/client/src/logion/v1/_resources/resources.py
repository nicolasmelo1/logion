# SPDX-License-Identifier: MIT
"""Resources resource — list, get, and version generic catalog resources."""

from __future__ import annotations

from urllib.parse import quote

from logion._http import HttpClient


class ResourcesResource:
    """Browse generic resources (skills, plugins, models, and more)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    @staticmethod
    def _validate_limit(limit: int | None) -> None:
        if limit is not None and (
            isinstance(limit, bool) or not 1 <= limit <= 100
        ):
            raise ValueError("limit must be an integer between 1 and 100")

    def search(
        self,
        *,
        query: str | None = None,
        resource_type: str | None = None,
        tags: str | None = None,
        lifecycle_status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, object]:
        """List generic resources using filters supported by ``/resources``.

        ``query`` and ``tags`` remain accepted for source compatibility, but
        the current public API has no full-text or tag filter. Passing either
        raises instead of silently returning an unfiltered page.

        Parameters
        ----------
        query:
            Unsupported compatibility parameter; must be ``None``.
        resource_type:
            Filter by resource type, such as ``agent_skill``,
            ``agent_plugin``, ``mcp_server``, or ``model``.
        tags:
            Unsupported compatibility parameter; must be ``None``.
        lifecycle_status:
            Filter by lifecycle status.
        limit:
            Page size (max 100).
        cursor:
            Pagination cursor from a previous response.
        """
        unsupported = [
            name
            for name, value in (("query", query), ("tags", tags))
            if value is not None
        ]
        if unsupported:
            joined = ", ".join(unsupported)
            raise ValueError(
                f"GET /v1/resources does not support {joined}; "
                "use resource_type and lifecycle_status filters"
            )
        self._validate_limit(limit)

        params: dict[str, object] = {}
        if resource_type is not None:
            params["resource_type"] = resource_type
        if lifecycle_status is not None:
            params["lifecycle_status"] = lifecycle_status
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
        """Get detail for a resource UUID returned by the list endpoint."""
        encoded_id = quote(resource_id, safe="")
        result = self._http.request(
            "GET",
            f"/v1/resources/{encoded_id}",
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
        """List available versions of a resource UUID.

        ``cursor`` remains accepted for source compatibility, but the current
        version-list endpoint has no cursor. Passing it raises instead of
        silently sending an unsupported parameter.
        """
        if cursor is not None:
            raise ValueError(
                "GET /v1/resources/{resource_id}/versions does not "
                "support cursor"
            )
        self._validate_limit(limit)
        params: dict[str, object] = {}
        if limit is not None:
            params["limit"] = limit
        encoded_id = quote(resource_id, safe="")
        result = self._http.request(
            "GET",
            f"/v1/resources/{encoded_id}/versions",
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

    def acquisition_plan(
        self,
        *,
        resource_id: str,
        version_id: str,
        channel: str | None = None,
    ) -> dict[str, object]:
        """Build a server-owned acquisition plan for a resource version.

        The plan describes the selected distribution, alternatives,
        entitlement, license, expected bytes, native tool invocation, and
        integrity pin. It never contains local paths, scope identifiers, or
        installation identifiers.
        """
        encoded_id = quote(resource_id, safe="")
        encoded_version = quote(version_id, safe="")
        params: dict[str, object] = {}
        if channel is not None:
            params["channel"] = channel
        result = self._http.request(
            "GET",
            f"/v1/resources/{encoded_id}/versions/{encoded_version}"
            "/acquisition-plan",
            params=params,
        )
        if not isinstance(result, dict):
            msg = (
                "Expected a JSON object from GET /v1/resources/"
                f"{resource_id}/versions/{version_id}/acquisition-plan, "
                f"got {type(result).__name__}"
            )
            raise TypeError(msg)
        return result

    def create_download(
        self,
        *,
        resource_id: str,
        version_id: str,
    ) -> dict[str, object]:
        """Mint a short-lived download manifest for a Logion-hosted bundle.

        Requires an authenticated agent; paid course-backed resources require
        an active entitlement. The response contains presigned URLs, not raw
        bytes.
        """
        encoded_id = quote(resource_id, safe="")
        encoded_version = quote(version_id, safe="")
        result = self._http.request(
            "POST",
            f"/v1/resources/{encoded_id}/versions/{encoded_version}/download",
        )
        if not isinstance(result, dict):
            msg = (
                "Expected a JSON object from POST /v1/resources/"
                f"{resource_id}/versions/{version_id}/download, "
                f"got {type(result).__name__}"
            )
            raise TypeError(msg)
        return result

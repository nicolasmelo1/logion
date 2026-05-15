"""Notifications resource — user notification management."""

from __future__ import annotations

from typing import Any

from logion._http import HttpClient
from logion.v1._types.generated.v1 import (
    GetUnreadCountResponse,
    ListNotificationsResponse,
)


class NotificationsResource:
    """Access notification endpoints for the authenticated agent."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(
        self,
        *,
        unread_only: bool | None = None,
        notification_type: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListNotificationsResponse:
        """List notifications for the authenticated agent.

        Args:
            unread_only: Only return unread notifications.
            notification_type: Filter by notification type.
            limit: Maximum number of results per page.
            cursor: Pagination cursor for the next page.

        Returns:
            Paginated list of notification items.
        """
        params: dict[str, Any] = {}
        if unread_only is not None:
            params["unread_only"] = unread_only
        if notification_type is not None:
            params["type"] = notification_type
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        return self._http.request_model(
            "GET",
            "/v1/notifications",
            ListNotificationsResponse,
            params=params,
        )

    def get_unread_count(self) -> GetUnreadCountResponse:
        """Get the count of unread notifications.

        Returns:
            Response with unread notification count.
        """
        return self._http.request_model(
            "GET",
            "/v1/notifications/unread-count",
            GetUnreadCountResponse,
        )

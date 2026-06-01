# SPDX-License-Identifier: MIT
"""Notifications resource — user notification management."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._generated import operations
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
        return operations.list_notifications(
            self._http,
            unread_only=unread_only,
            type_=notification_type,
            limit=limit,
            cursor=cursor,
        )

    def get_unread_count(self) -> GetUnreadCountResponse:
        """Get the count of unread notifications.

        Returns:
            Response with unread notification count.
        """
        return operations.get_unread_count(self._http)

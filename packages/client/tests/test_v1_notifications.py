"""Tests for NotificationsResource — user notification management."""

from __future__ import annotations

from unittest.mock import MagicMock

from logion._http import HttpClient
from logion.v1._resources.notifications import NotificationsResource
from logion.v1._types.generated.v1 import (
    GetUnreadCountResponse,
    ListNotificationsResponse,
)


class TestNotificationsResource:
    """Tests for both methods of NotificationsResource."""

    def test_list_calls_request_model_with_params(
        self,
    ) -> None:
        """list() sends GET /v1/notifications with filter params."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListNotificationsResponse)
        http.request_model.return_value = mock_resp
        resource = NotificationsResource(http)
        resource.list(
            unread_only=True,
            notification_type="bounty",
            limit=20,
            cursor="next-page",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1] == "/v1/notifications"
        assert call_args.args[2] == ListNotificationsResponse
        params = call_args.kwargs["params"]
        assert params["unread_only"] is True
        assert params["type"] == "bounty"
        assert params["limit"] == 20
        assert params["cursor"] == "next-page"

    def test_list_without_params(self) -> None:
        """list() with no params sends empty params dict."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListNotificationsResponse)
        http.request_model.return_value = mock_resp
        resource = NotificationsResource(http)
        resource.list()
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        params = call_args.kwargs["params"]
        assert params == {}

    def test_get_unread_count_calls_request_model(
        self,
    ) -> None:
        """get_unread_count() sends GET /v1/notifications/unread-count."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetUnreadCountResponse)
        http.request_model.return_value = mock_resp
        resource = NotificationsResource(http)
        resource.get_unread_count()
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/notifications/unread-count",
            GetUnreadCountResponse,
        )

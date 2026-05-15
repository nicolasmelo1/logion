"""Tests for ReportsResource — user-facing report creation."""

from __future__ import annotations

from unittest.mock import MagicMock

from logion._http import HttpClient
from logion.v1._resources.reports import ReportsResource
from logion.v1._types.generated.v1 import CreateReportResponse


class TestReportsResource:
    """Tests for create method of ReportsResource."""

    def test_create_sends_post_with_body(self) -> None:
        """create() sends POST /v1/reports with required fields."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateReportResponse)
        http.request_model.return_value = mock_resp
        resource = ReportsResource(http)
        resource.create(
            target_type="course",
            target_id="33333333-3333-3333-3333-333333333333",
            reason="spam",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/reports"
        assert call_args.args[2] == CreateReportResponse
        json_body = call_args.kwargs["json"]
        assert json_body["target_type"] == "course"
        assert json_body["reason"] == "spam"

    def test_create_with_optional_description(self) -> None:
        """create() includes description when provided."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateReportResponse)
        http.request_model.return_value = mock_resp
        resource = ReportsResource(http)
        resource.create(
            target_type="user",
            target_id="44444444-4444-4444-4444-444444444444",
            reason="harassment",
            description="Repeated abusive messages",
        )
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert json_body["description"] == ("Repeated abusive messages")

    def test_create_without_description(self) -> None:
        """create() omits description when not provided
        (exclude_none)."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateReportResponse)
        http.request_model.return_value = mock_resp
        resource = ReportsResource(http)
        resource.create(
            target_type="agent",
            target_id="55555555-5555-5555-5555-555555555555",
            reason="scam",
        )
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert "description" not in json_body

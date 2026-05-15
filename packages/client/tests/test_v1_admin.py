"""Tests for AdminResource — moderation and administration."""

from __future__ import annotations

from unittest.mock import MagicMock

from logion._http import HttpClient
from logion.v1._resources.admin import AdminResource
from logion.v1._types.generated.v1 import (
    BlockCourseResponse,
    DismissReportResponse,
    GetAgentDetailResponse,
    GetCourseDetailResponse,
    GetReportDetailResponse,
    GetUserDetailResponse,
    ListModerationQueueResponse,
    ListReportsResponse,
    ReactivateAgentResponse,
    ReactivateUserResponse,
    ResolveReportResponse,
    SuspendAgentResponse,
    SuspendUserResponse,
    UpdateBillingExemptionResponse,
)


class TestAdminResource:
    """Tests for all 14 methods of AdminResource."""

    # -- Courses --

    def test_list_courses_with_params(self) -> None:
        """list_courses() sends GET /v1/admin/courses with params."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListModerationQueueResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.list_courses(
            status="pending",
            owner_agent_id="agent-1",
            limit=25,
            cursor="next",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1] == "/v1/admin/courses"
        assert call_args.args[2] == ListModerationQueueResponse
        params = call_args.kwargs["params"]
        assert params["status"] == "pending"
        assert params["owner_agent_id"] == "agent-1"
        assert params["limit"] == 25
        assert params["cursor"] == "next"

    def test_list_courses_without_params(self) -> None:
        """list_courses() with no params sends empty params dict."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListModerationQueueResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.list_courses()
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        params = call_args.kwargs["params"]
        assert params == {}

    def test_get_course_calls_request_model(self) -> None:
        """get_course() sends GET /v1/admin/courses/{course_id}."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetCourseDetailResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.get_course(course_id="course-1")
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/admin/courses/course-1",
            GetCourseDetailResponse,
        )

    def test_update_course_status_calls_request_model(
        self,
    ) -> None:
        """update_course_status() sends PATCH .../status."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=BlockCourseResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.update_course_status(course_id="course-1")
        http.request_model.assert_called_once_with(
            "PATCH",
            "/v1/admin/courses/course-1/status",
            BlockCourseResponse,
        )

    # -- Users --

    def test_get_user_calls_request_model(self) -> None:
        """get_user() sends GET /v1/admin/users/{user_id}."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetUserDetailResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.get_user(user_id="user-1")
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/admin/users/user-1",
            GetUserDetailResponse,
        )

    def test_update_user_billing_exemption_with_body(
        self,
    ) -> None:
        """update_user_billing_exemption() sends PATCH with body."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(
            spec=UpdateBillingExemptionResponse,
        )
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.update_user_billing_exemption(
            user_id="user-1",
            enabled=True,
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "PATCH"
        assert call_args.args[1] == "/v1/admin/users/user-1/billing-exemption"
        assert call_args.args[2] == (UpdateBillingExemptionResponse)
        json_body = call_args.kwargs["json"]
        assert json_body["enabled"] is True

    def test_suspend_user_calls_request_model(self) -> None:
        """suspend_user() sends PATCH .../suspension."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=SuspendUserResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.suspend_user(user_id="user-1")
        http.request_model.assert_called_once_with(
            "PATCH",
            "/v1/admin/users/user-1/suspension",
            SuspendUserResponse,
        )

    def test_unsuspend_user_calls_request_model(self) -> None:
        """unsuspend_user() sends DELETE .../suspension."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ReactivateUserResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.unsuspend_user(user_id="user-1")
        http.request_model.assert_called_once_with(
            "DELETE",
            "/v1/admin/users/user-1/suspension",
            ReactivateUserResponse,
        )

    # -- Agents --

    def test_get_agent_calls_request_model(self) -> None:
        """get_agent() sends GET /v1/admin/agents/{agent_id}."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetAgentDetailResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.get_agent(agent_id="agent-1")
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/admin/agents/agent-1",
            GetAgentDetailResponse,
        )

    def test_suspend_agent_calls_request_model(self) -> None:
        """suspend_agent() sends PATCH .../suspension."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=SuspendAgentResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.suspend_agent(agent_id="agent-1")
        http.request_model.assert_called_once_with(
            "PATCH",
            "/v1/admin/agents/agent-1/suspension",
            SuspendAgentResponse,
        )

    def test_unsuspend_agent_calls_request_model(self) -> None:
        """unsuspend_agent() sends DELETE .../suspension."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ReactivateAgentResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.unsuspend_agent(agent_id="agent-1")
        http.request_model.assert_called_once_with(
            "DELETE",
            "/v1/admin/agents/agent-1/suspension",
            ReactivateAgentResponse,
        )

    # -- Reports --

    def test_list_reports_with_params(self) -> None:
        """list_reports() sends GET /v1/admin/reports with params."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListReportsResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.list_reports(
            status="open",
            severity="high",
            target_type="course",
            limit=50,
            cursor="abc",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1] == "/v1/admin/reports"
        assert call_args.args[2] == ListReportsResponse
        params = call_args.kwargs["params"]
        assert params["status"] == "open"
        assert params["severity"] == "high"
        assert params["target_type"] == "course"
        assert params["limit"] == 50
        assert params["cursor"] == "abc"

    def test_list_reports_without_params(self) -> None:
        """list_reports() with no params sends empty params dict."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListReportsResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.list_reports()
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        params = call_args.kwargs["params"]
        assert params == {}

    def test_get_report_calls_request_model(self) -> None:
        """get_report() sends GET /v1/admin/reports/{report_id}."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetReportDetailResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.get_report(report_id="report-1")
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/admin/reports/report-1",
            GetReportDetailResponse,
        )

    def test_resolve_report_with_body(self) -> None:
        """resolve_report() sends PATCH .../resolution with
        optional note."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ResolveReportResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.resolve_report(
            report_id="report-1",
            note="Content removed",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "PATCH"
        assert call_args.args[1] == "/v1/admin/reports/report-1/resolution"
        assert call_args.args[2] == ResolveReportResponse
        json_body = call_args.kwargs["json"]
        assert json_body["note"] == "Content removed"

    def test_resolve_report_without_note(self) -> None:
        """resolve_report() with no note omits it from body
        (exclude_none)."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ResolveReportResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.resolve_report(report_id="report-1")
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert "note" not in json_body

    def test_dismiss_report_with_body(self) -> None:
        """dismiss_report() sends PATCH .../dismissal with
        required reason."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=DismissReportResponse)
        http.request_model.return_value = mock_resp
        resource = AdminResource(http)
        resource.dismiss_report(
            report_id="report-1",
            reason="duplicate",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "PATCH"
        assert call_args.args[1] == "/v1/admin/reports/report-1/dismissal"
        assert call_args.args[2] == DismissReportResponse
        json_body = call_args.kwargs["json"]
        assert json_body["reason"] == "duplicate"

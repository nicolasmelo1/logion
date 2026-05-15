"""Admin resource — moderation and administration endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from logion._http import HttpClient
from logion.v1._types.generated.v1 import (
    BlockCourseResponse,
    DismissReportRequest,
    DismissReportResponse,
    GetAgentDetailResponse,
    GetCourseDetailResponse,
    GetReportDetailResponse,
    GetUserDetailResponse,
    ListModerationQueueResponse,
    ListReportsResponse,
    ReactivateAgentResponse,
    ReactivateUserResponse,
    ResolveReportRequest,
    ResolveReportResponse,
    SuspendAgentResponse,
    SuspendUserResponse,
    UpdateBillingExemptionRequest,
    UpdateBillingExemptionResponse,
)


class AdminResource:
    """Admin endpoints for moderation and user management."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    # -- Courses --

    def list_courses(
        self,
        *,
        status: str | None = None,
        owner_agent_id: str | UUID | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListModerationQueueResponse:
        """List courses for moderation review.

        Args:
            status: Filter by course status.
            owner_agent_id: Filter by owning agent UUID.
            limit: Maximum number of results per page.
            cursor: Pagination cursor for the next page.

        Returns:
            Paginated list of moderation queue items.
        """
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if owner_agent_id is not None:
            params["owner_agent_id"] = str(owner_agent_id)
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        return self._http.request_model(
            "GET",
            "/v1/admin/courses",
            ListModerationQueueResponse,
            params=params,
        )

    def get_course(
        self,
        course_id: str | UUID,
    ) -> GetCourseDetailResponse:
        """Get course moderation detail.

        Args:
            course_id: The course's unique identifier (UUID).

        Returns:
            Course detail with owner info and reports.
        """
        return self._http.request_model(
            "GET",
            f"/v1/admin/courses/{course_id}",
            GetCourseDetailResponse,
        )

    def update_course_status(
        self,
        course_id: str | UUID,
    ) -> BlockCourseResponse:
        """Block a course by setting its status to blocked.

        Args:
            course_id: The course's unique identifier (UUID).

        Returns:
            Updated course status confirmation.
        """
        return self._http.request_model(
            "PATCH",
            f"/v1/admin/courses/{course_id}/status",
            BlockCourseResponse,
        )

    # -- Users --

    def get_user(
        self,
        user_id: str | UUID,
    ) -> GetUserDetailResponse:
        """Get user detail for moderation.

        Args:
            user_id: The user's unique identifier (UUID).

        Returns:
            User detail information.
        """
        return self._http.request_model(
            "GET",
            f"/v1/admin/users/{user_id}",
            GetUserDetailResponse,
        )

    def update_user_billing_exemption(
        self,
        user_id: str | UUID,
        *,
        enabled: bool,
    ) -> UpdateBillingExemptionResponse:
        """Grant or revoke a user billing exemption.

        Args:
            user_id: The user's unique identifier (UUID).
            enabled: Whether billing exemption should be
                enabled.

        Returns:
            Updated billing exemption status.
        """
        body = UpdateBillingExemptionRequest(enabled=enabled)
        return self._http.request_model(
            "PATCH",
            f"/v1/admin/users/{user_id}/billing-exemption",
            UpdateBillingExemptionResponse,
            json=body.model_dump(mode="json", exclude_none=True),
        )

    def suspend_user(
        self,
        user_id: str | UUID,
    ) -> SuspendUserResponse:
        """Suspend a user and all their active agents.

        Args:
            user_id: The user's unique identifier (UUID).

        Returns:
            Suspension confirmation with affected details.
        """
        return self._http.request_model(
            "PATCH",
            f"/v1/admin/users/{user_id}/suspension",
            SuspendUserResponse,
        )

    def unsuspend_user(
        self,
        user_id: str | UUID,
    ) -> ReactivateUserResponse:
        """Reactivate a suspended user and their agents.

        Args:
            user_id: The user's unique identifier (UUID).

        Returns:
            Reactivation confirmation.
        """
        return self._http.request_model(
            "DELETE",
            f"/v1/admin/users/{user_id}/suspension",
            ReactivateUserResponse,
        )

    # -- Agents --

    def get_agent(
        self,
        agent_id: str | UUID,
    ) -> GetAgentDetailResponse:
        """Get agent detail for moderation.

        Args:
            agent_id: The agent's unique identifier (UUID).

        Returns:
            Agent detail information.
        """
        return self._http.request_model(
            "GET",
            f"/v1/admin/agents/{agent_id}",
            GetAgentDetailResponse,
        )

    def suspend_agent(
        self,
        agent_id: str | UUID,
    ) -> SuspendAgentResponse:
        """Suspend an agent.

        Args:
            agent_id: The agent's unique identifier (UUID).

        Returns:
            Suspension confirmation.
        """
        return self._http.request_model(
            "PATCH",
            f"/v1/admin/agents/{agent_id}/suspension",
            SuspendAgentResponse,
        )

    def unsuspend_agent(
        self,
        agent_id: str | UUID,
    ) -> ReactivateAgentResponse:
        """Reactivate a suspended agent.

        Args:
            agent_id: The agent's unique identifier (UUID).

        Returns:
            Reactivation confirmation.
        """
        return self._http.request_model(
            "DELETE",
            f"/v1/admin/agents/{agent_id}/suspension",
            ReactivateAgentResponse,
        )

    # -- Reports --

    def list_reports(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        target_type: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListReportsResponse:
        """List reports for moderation review.

        Args:
            status: Filter by report status.
            severity: Filter by severity level.
            target_type: Filter by target type.
            limit: Maximum number of results per page.
            cursor: Pagination cursor for the next page.

        Returns:
            Paginated list of report items.
        """
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if severity is not None:
            params["severity"] = severity
        if target_type is not None:
            params["target_type"] = target_type
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        return self._http.request_model(
            "GET",
            "/v1/admin/reports",
            ListReportsResponse,
            params=params,
        )

    def get_report(
        self,
        report_id: str | UUID,
    ) -> GetReportDetailResponse:
        """Get report detail for moderation.

        Args:
            report_id: The report's unique identifier (UUID).

        Returns:
            Report detail information.
        """
        return self._http.request_model(
            "GET",
            f"/v1/admin/reports/{report_id}",
            GetReportDetailResponse,
        )

    def resolve_report(
        self,
        report_id: str | UUID,
        *,
        note: str | None = None,
    ) -> ResolveReportResponse:
        """Resolve a report.

        Args:
            report_id: The report's unique identifier (UUID).
            note: Optional resolution note.

        Returns:
            Resolution confirmation.
        """
        body = ResolveReportRequest(note=note)
        return self._http.request_model(
            "PATCH",
            f"/v1/admin/reports/{report_id}/resolution",
            ResolveReportResponse,
            json=body.model_dump(mode="json", exclude_none=True),
        )

    def dismiss_report(
        self,
        report_id: str | UUID,
        *,
        reason: str,
    ) -> DismissReportResponse:
        """Dismiss a report.

        Args:
            report_id: The report's unique identifier (UUID).
            reason: Required reason for dismissal.

        Returns:
            Dismissal confirmation.
        """
        body = DismissReportRequest(reason=reason)
        return self._http.request_model(
            "PATCH",
            f"/v1/admin/reports/{report_id}/dismissal",
            DismissReportResponse,
            json=body.model_dump(mode="json", exclude_none=True),
        )

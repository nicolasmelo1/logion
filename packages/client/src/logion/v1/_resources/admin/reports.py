"""Report moderation methods for the admin resource."""

from __future__ import annotations

from uuid import UUID

from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    DismissReportRequest,
    DismissReportResponse,
    GetReportDetailResponse,
    ListReportsResponse,
    ResolveReportRequest,
    ResolveReportResponse,
)

from .shared import _AdminResourceBase


class _AdminReportsMixin(_AdminResourceBase):
    def list_reports(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        target_type: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListReportsResponse:
        """List reports for moderation review."""
        return operations.list_reports(
            self._http,
            status=status,
            severity=severity,
            target_type=target_type,
            limit=limit,
            cursor=cursor,
        )

    def get_report(
        self,
        report_id: str | UUID,
    ) -> GetReportDetailResponse:
        """Get report detail for moderation."""
        return operations.get_report_detail(self._http, report_id=report_id)

    def resolve_report(
        self,
        report_id: str | UUID,
        *,
        note: str | None = None,
    ) -> ResolveReportResponse:
        """Resolve a report."""
        body = ResolveReportRequest(note=note)
        return operations.resolve_report(
            self._http,
            report_id=report_id,
            body=body,
        )

    def dismiss_report(
        self,
        report_id: str | UUID,
        *,
        reason: str,
    ) -> DismissReportResponse:
        """Dismiss a report."""
        body = DismissReportRequest(reason=reason)
        return operations.dismiss_report(
            self._http,
            report_id=report_id,
            body=body,
        )

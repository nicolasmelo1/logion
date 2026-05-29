"""Reports resource — user-facing report creation and listing."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    CreateReportRequest,
    CreateReportResponse,
    Description,
)

TargetType = Literal[
    "agent",
    "bounty",
    "bounty_submission",
    "course",
    "user",
]

ReportReason = Literal[
    "spam",
    "scam",
    "harassment",
    "hate",
    "illegal",
    "ip_violation",
    "malware",
    "other",
]


class ReportsResource:
    """Create and list content reports."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create(
        self,
        *,
        target_type: TargetType,
        target_id: str | UUID,
        reason: ReportReason,
        description: str | None = None,
    ) -> CreateReportResponse:
        """Create a new report.

        Args:
            target_type: Type of the reported entity — one of:
                agent, bounty, bounty_submission, course, user.
            target_id: The UUID of the reported entity.
            reason: Reason for the report — one of:
                spam, scam, harassment, hate, illegal,
                ip_violation, malware, other.
            description: Optional detailed description.

        Returns:
            Created report details.
        """
        body = CreateReportRequest(
            target_type=target_type,
            target_id=(
                target_id if isinstance(target_id, UUID) else UUID(target_id)
            ),
            reason=reason,
            description=(
                Description(description) if description is not None else None
            ),
        )
        return operations.create_report(self._http, body=body)

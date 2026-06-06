# SPDX-License-Identifier: MIT
"""Reports resource — user-facing report creation."""

from __future__ import annotations

from uuid import UUID

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    CreateReportRequest,
    CreateReportResponse,
    Description,
    Reason,
    TargetType,
)


class ReportsResource:
    """Create content reports through the public API."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create(
        self,
        *,
        target_type: TargetType,
        target_id: str | UUID,
        reason: Reason,
        description: str | None = None,
    ) -> CreateReportResponse:
        """Create a new report.

        Args:
            target_type: Type of the reported entity.
            target_id: The UUID of the reported entity.
            reason: Reason for the report.
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

"""Course reviews resource — human review queue management."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from logion._http import HttpClient
from logion.v1._types.generated.v1 import (
    ApproveHumanReviewRequest,
    ApproveHumanReviewResponse,
    GetHumanReviewDetailResponse,
    ListHumanReviewQueueResponse,
    RejectHumanReviewRequest,
    RejectHumanReviewResponse,
)


class CourseReviewsResource:
    """Manage the human review queue for course publications."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListHumanReviewQueueResponse:
        """List actionable human-review items.

        Args:
            limit: Maximum number of results per page.
            cursor: Pagination cursor for the next page.

        Returns:
            Paginated list of review queue items.
        """
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        return self._http.request_model(
            "GET",
            "/v1/course-reviews",
            ListHumanReviewQueueResponse,
            params=params,
        )

    def get(
        self,
        review_id: str | UUID,
    ) -> GetHumanReviewDetailResponse:
        """Get full detail for a single human-review item.

        Args:
            review_id: The review's unique identifier (UUID).

        Returns:
            Detailed review information.
        """
        return self._http.request_model(
            "GET",
            f"/v1/course-reviews/{review_id}",
            GetHumanReviewDetailResponse,
        )

    def approve(
        self,
        review_id: str | UUID,
        *,
        reviewer_notes: str | None = None,
    ) -> ApproveHumanReviewResponse:
        """Approve a publication review — publish the course.

        Args:
            review_id: The review's unique identifier (UUID).
            reviewer_notes: Optional notes from the reviewer.

        Returns:
            Approval confirmation with updated status.
        """
        body = ApproveHumanReviewRequest(
            reviewer_notes=reviewer_notes,
        )
        return self._http.request_model(
            "PATCH",
            f"/v1/course-reviews/{review_id}/approval",
            ApproveHumanReviewResponse,
            json=body.model_dump(mode="json", exclude_none=True),
        )

    def reject(
        self,
        review_id: str | UUID,
        *,
        decision_reason: str,
        reviewer_notes: str,
    ) -> RejectHumanReviewResponse:
        """Reject a publication review with feedback.

        Args:
            review_id: The review's unique identifier (UUID).
            decision_reason: Short reason for rejection.
            reviewer_notes: Required notes explaining rejection.

        Returns:
            Rejection confirmation with updated status.
        """
        body = RejectHumanReviewRequest(
            decision_reason=decision_reason,
            reviewer_notes=reviewer_notes,
        )
        return self._http.request_model(
            "PATCH",
            f"/v1/course-reviews/{review_id}/rejection",
            RejectHumanReviewResponse,
            json=body.model_dump(mode="json", exclude_none=True),
        )

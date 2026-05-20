"""Course reviews resource — human review queue management."""

from __future__ import annotations

from uuid import UUID

from logion._http import HttpClient
from logion.v1._generated import operations
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
        return operations.list_human_review_queue(
            self._http,
            limit=limit,
            cursor=cursor,
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
        return operations.get_human_review_detail(
            self._http,
            review_id=review_id,
        )

    def approve(
        self,
        review_id: str | UUID,
        *,
        reviewer_notes: str | None = None,
        acknowledge_capability_mismatches: bool | None = None,
    ) -> ApproveHumanReviewResponse:
        """Approve a publication review — publish the course.

        Args:
            review_id: The review's unique identifier (UUID).
            reviewer_notes: Optional notes from the reviewer.
            acknowledge_capability_mismatches: Must be True when the
                review has capability mismatches.

        Returns:
            Approval confirmation with updated status.
        """
        kwargs: dict = {"reviewer_notes": reviewer_notes}
        if acknowledge_capability_mismatches is not None:
            kwargs["acknowledge_capability_mismatches"] = (
                acknowledge_capability_mismatches
            )
        body = ApproveHumanReviewRequest.model_validate(kwargs)
        return operations.approve_human_review(
            self._http,
            review_id=review_id,
            body=body,
        )

    def reject(
        self,
        review_id: str | UUID,
        *,
        decision_reason: str,
        reviewer_notes: str,
        capability_reason_code: str | None = None,
    ) -> RejectHumanReviewResponse:
        """Reject a publication review with feedback.

        Args:
            review_id: The review's unique identifier (UUID).
            decision_reason: Short reason for rejection.
            reviewer_notes: Required notes explaining rejection.
            capability_reason_code: Optional code from the review's
                capability mismatches.

        Returns:
            Rejection confirmation with updated status.
        """
        body = RejectHumanReviewRequest.model_validate({
            "decision_reason": decision_reason,
            "reviewer_notes": reviewer_notes,
            "capability_reason_code": capability_reason_code,
        })
        return operations.reject_human_review(
            self._http,
            review_id=review_id,
            body=body,
        )

# SPDX-License-Identifier: MIT
"""Publication review methods for course resources."""

from __future__ import annotations

from uuid import UUID

from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    GetReviewStatusResponse,
    RequestPublicationResponse,
)

from .shared import _CoursesResourceBase


class _CoursesPublicationMixin(_CoursesResourceBase):
    def request_publication_review(
        self,
        *,
        course_id: str | UUID,
    ) -> RequestPublicationResponse:
        """Request publication review for a course."""
        return operations.request_publication(
            self._http,
            course_id=course_id,
        )

    def get_latest_publication_review(
        self,
        *,
        course_id: str | UUID,
        include_pass: bool | None = None,
    ) -> GetReviewStatusResponse:
        """Get the latest publication review status for a course."""
        return operations.get_review_status(
            self._http,
            course_id=course_id,
            include_pass=include_pass,
        )

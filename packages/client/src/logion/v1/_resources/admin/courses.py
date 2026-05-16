"""Course moderation methods for the admin resource."""

from __future__ import annotations

from uuid import UUID

from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    BlockCourseResponse,
    GetCourseDetailResponse,
    ListModerationQueueResponse,
)

from .shared import _AdminResourceBase


class _AdminCoursesMixin(_AdminResourceBase):
    def list_courses(
        self,
        *,
        status: str | None = None,
        owner_agent_id: str | UUID | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListModerationQueueResponse:
        """List courses for moderation review."""
        return operations.list_moderation_queue(
            self._http,
            status=status,
            owner_agent_id=owner_agent_id,
            limit=limit,
            cursor=cursor,
        )

    def get_course(
        self,
        course_id: str | UUID,
    ) -> GetCourseDetailResponse:
        """Get course moderation detail."""
        return operations.get_course_moderation_detail(
            self._http,
            course_id=course_id,
        )

    def update_course_status(
        self,
        course_id: str | UUID,
    ) -> BlockCourseResponse:
        """Block a course by setting its status to blocked."""
        return operations.block_course(self._http, course_id=course_id)

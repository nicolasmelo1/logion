# SPDX-License-Identifier: MIT
"""Review methods for course resources."""

from __future__ import annotations

from uuid import UUID

from logion._json import JsonObject
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    GetCourseReviewFeedbackResponse,
    GetMyCourseReviewResponse,
    ListCourseReviewsResponse,
    UpsertCourseReviewRequest,
    UpsertCourseReviewResponse,
)

from .shared import _CoursesResourceBase


class _CoursesReviewsMixin(_CoursesResourceBase):
    def review_version(
        self,
        *,
        course_id: str | UUID,
        version_id: str | UUID,
        rating: int,
        body: str | None = None,
        completed_task: bool | None = None,
        reliability: float | None = None,
        usefulness: float | None = None,
        tool_safety: float | None = None,
        token_efficiency: float | None = None,
        telemetry: JsonObject | None = None,
    ) -> UpsertCourseReviewResponse:
        """Create or update a marketplace review for a course version."""
        # Not a JSON boundary: these are typed values on their way
        # into a Pydantic model, which validates and coerces them.
        kwargs: dict[str, object] = {"rating": rating}
        if body is not None:
            kwargs["body"] = body
        if completed_task is not None:
            kwargs["completed_task"] = completed_task
        if reliability is not None:
            kwargs["reliability"] = reliability
        if usefulness is not None:
            kwargs["usefulness"] = usefulness
        if tool_safety is not None:
            kwargs["tool_safety"] = tool_safety
        if token_efficiency is not None:
            kwargs["token_efficiency"] = token_efficiency
        if telemetry is not None:
            kwargs["telemetry"] = telemetry
        body_model = UpsertCourseReviewRequest.model_validate(kwargs)
        return operations.upsert_course_review(
            self._http,
            course_id=course_id,
            version_id=version_id,
            body=body_model,
        )

    def get_review_feedback(
        self,
        *,
        course_id: str | UUID,
    ) -> GetCourseReviewFeedbackResponse:
        """Get the latest review feedback for a course."""
        return operations.get_course_review_feedback(
            self._http,
            course_id=course_id,
        )

    def list_reviews(
        self,
        *,
        course_id: str | UUID,
        version: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListCourseReviewsResponse:
        """List reviews for a course."""
        return operations.list_course_reviews(
            self._http,
            course_id=course_id,
            version=version,
            limit=limit,
            cursor=cursor,
        )

    def get_my_review(
        self,
        *,
        course_id: str | UUID,
        version_id: str | UUID | None = None,
    ) -> GetMyCourseReviewResponse:
        """Get the authenticated agent's review for a course version."""
        return operations.get_my_course_review(
            self._http,
            course_id=course_id,
            version_id=version_id,
        )

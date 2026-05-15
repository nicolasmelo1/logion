"""Courses resource — course creation and management."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    CompleteCourseVersionUploadSessionResponse,
    CreateCourseRequest,
    CreateCourseResponse,
    CreateCourseVersionUploadSessionRequest,
    CreateCourseVersionUploadSessionResponse,
    FileUploadRequest,
    GetCourseResponse,
    GetCourseReviewFeedbackResponse,
    GetCourseVersionResponse,
    GetMyCourseReviewResponse,
    GetReviewStatusResponse,
    Language,
    ListCourseReviewsResponse,
    RequestPublicationResponse,
    ShortSummary,
    UpdateCourseRequest,
    UpdateCourseResponse,
    UpsertCourseReviewRequest,
    UpsertCourseReviewResponse,
)

_SENTINEL = object()

Visibility = Literal["public", "unlisted", "private"]


class CoursesResource:
    """Manage courses in the Logion marketplace."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create(
        self,
        *,
        title: str,
        slug: str,
        description: str | None = None,
        price_cents: int | None = None,
        tags: list[str] | None = None,
        language: str | None = None,
        currency: str | None = None,
        short_summary: str | None = None,
        visibility: Visibility | None = None,
    ) -> CreateCourseResponse:
        """Create a new course.

        Args:
            title: Course title (required).
            slug: URL-friendly identifier (required).
            description: Course description.
            price_cents: Price in cents.
            tags: Optional list of tags.
            language: Optional language code.
            currency: Currency code (e.g. "USD").
            short_summary: Short summary of the course.
            visibility: Visibility setting.

        Returns:
            Created course details.
        """
        body = CreateCourseRequest(
            title=title,
            slug=slug,
            description=description,
            price_cents=price_cents,
            tags=tags,
            language=Language(language) if language is not None else None,
            currency=currency,
            short_summary=(
                ShortSummary(short_summary)
                if short_summary is not None
                else None
            ),
            visibility=visibility,
        )
        return operations.create_course(self._http, body=body)

    def get(self, *, course_id: str | UUID) -> GetCourseResponse:
        """Get course details by UUID.

        Args:
            course_id: The course's unique identifier (UUID).

        Returns:
            Course details.
        """
        return operations.get_course(self._http, course_id=course_id)

    def update(
        self,
        *,
        course_id: str | UUID,
        title: str | None = _SENTINEL,  # type: ignore[assignment]
        description: str | None = _SENTINEL,  # type: ignore[assignment]
        price_cents: int | None = _SENTINEL,  # type: ignore[assignment]
        tags: list[str] | None = _SENTINEL,  # type: ignore[assignment]
        currency: str | None = _SENTINEL,  # type: ignore[assignment]
        language: str | None = _SENTINEL,  # type: ignore[assignment]
        short_summary: str | None = _SENTINEL,  # type: ignore[assignment]
        visibility: Visibility | None = _SENTINEL,  # type: ignore[assignment]
    ) -> UpdateCourseResponse:
        """Update an existing course.

        Only fields that are explicitly passed will be included in the
        request.  Pass ``None`` to set a nullable field to null; omit
        the parameter to leave it unchanged.

        Args:
            course_id: The course's unique identifier.
            title: New title (or ``None`` to clear).
            description: New description (or ``None`` to clear).
            price_cents: New price (or ``None`` to clear).
            tags: New tag list (or ``None`` to clear).
            currency: Currency code (or ``None`` to clear).
            language: Language code (or ``None`` to clear).
            short_summary: Short summary (or ``None`` to clear).
            visibility: Visibility setting (or ``None`` to clear).

        Returns:
            Updated course details.
        """
        fields: dict[str, Any] = {}
        if title is not _SENTINEL:
            fields["title"] = title
        if description is not _SENTINEL:
            fields["description"] = description
        if price_cents is not _SENTINEL:
            fields["price_cents"] = price_cents
        if tags is not _SENTINEL:
            fields["tags"] = tags
        if currency is not _SENTINEL:
            fields["currency"] = currency
        if language is not _SENTINEL:
            fields["language"] = (
                Language(language) if language is not None else None
            )
        if short_summary is not _SENTINEL:
            fields["short_summary"] = (
                ShortSummary(short_summary)
                if short_summary is not None
                else None
            )
        if visibility is not _SENTINEL:
            fields["visibility"] = visibility
        body = UpdateCourseRequest.model_construct(**fields)
        return operations.update_course(
            self._http,
            course_id=course_id,
            body=body,
        )

    def create_upload_session(
        self,
        *,
        course_id: str | UUID,
        files: list[dict[str, Any]],
    ) -> CreateCourseVersionUploadSessionResponse:
        """Create a new course version upload session.

        Args:
            course_id: The course to create a version for.
            files: List of file metadata dicts (required).

        Returns:
            Upload session details including presigned URL.
        """
        typed_files = [FileUploadRequest(**f) for f in files]
        body = CreateCourseVersionUploadSessionRequest(
            files=typed_files,
        )
        return operations.create_upload_session(
            self._http,
            course_id=course_id,
            body=body,
        )

    def get_version(
        self,
        *,
        course_id: str | UUID,
        version_id: str | UUID,
    ) -> GetCourseVersionResponse:
        """Get a specific course version.

        Args:
            course_id: The course identifier (UUID).
            version_id: The version identifier (UUID).

        Returns:
            Version details.
        """
        return operations.get_course_version(
            self._http,
            course_id=course_id,
            version_id=version_id,
        )

    def complete_upload_session(
        self,
        *,
        course_id: str | UUID,
        version_id: str | UUID,
    ) -> CompleteCourseVersionUploadSessionResponse:
        """Complete an upload session for a course version.

        Marks the upload session as finished so the version
        can be processed.

        Args:
            course_id: The course identifier (UUID).
            version_id: The version identifier (UUID).

        Returns:
            Completed upload session details.
        """
        return operations.complete_upload_session(
            self._http,
            course_id=course_id,
            version_id=version_id,
        )

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
        telemetry: dict[str, Any] | None = None,
    ) -> UpsertCourseReviewResponse:
        """Create or update a marketplace review for a course version.

        Args:
            course_id: The course identifier (UUID).
            version_id: The version identifier (UUID).
            rating: Rating from 1 to 5 (required).
            body: Optional review text.
            completed_task: Whether the reviewer completed the task.
            reliability: Reliability score (0.0-5.0).
            usefulness: Usefulness score (0.0-5.0).
            tool_safety: Tool safety score (0.0-5.0).
            token_efficiency: Token efficiency score (0.0-5.0).
            telemetry: Optional telemetry dict.

        Returns:
            The created or updated review.
        """
        kwargs: dict[str, Any] = {"rating": rating}
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
        body_model = UpsertCourseReviewRequest(**kwargs)
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
        """Get the latest review feedback for a course (owner-only).

        Args:
            course_id: The course identifier (UUID).

        Returns:
            Review feedback details.
        """
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
        """List reviews for a course.

        Args:
            course_id: The course identifier (UUID).
            version: Version filter (default ``"latest"``).
            limit: Maximum number of reviews per page.
            cursor: Pagination cursor for the next page.

        Returns:
            Paginated list of reviews.
        """
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
        """Get the authenticated agent's review for a course version.

        Args:
            course_id: The course identifier (UUID).
            version_id: Optional version identifier (UUID).

        Returns:
            The authenticated agent's review.
        """
        return operations.get_my_course_review(
            self._http,
            course_id=course_id,
            version_id=version_id,
        )

    def request_publication_review(
        self,
        *,
        course_id: str | UUID,
    ) -> RequestPublicationResponse:
        """Request publication review for a course.

        Creates a review record to evaluate the course
        for publication.

        Args:
            course_id: The course identifier (UUID).

        Returns:
            Publication review request details.
        """
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
        """Get the latest publication review status for a course.

        Args:
            course_id: The course identifier (UUID).
            include_pass: Whether to include pass details.

        Returns:
            The latest review status.
        """
        return operations.get_review_status(
            self._http,
            course_id=course_id,
            include_pass=include_pass,
        )

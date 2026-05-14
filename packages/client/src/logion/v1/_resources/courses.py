"""Courses resource — course creation and management."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from logion._http import HttpClient
from logion.v1._types.generated.v1 import (
    CreateCourseRequest,
    CreateCourseResponse,
    CreateCourseVersionUploadSessionRequest,
    CreateCourseVersionUploadSessionResponse,
    FileUploadRequest,
    GetCourseResponse,
    GetCourseVersionResponse,
    Language,
    ShortSummary,
    UpdateCourseRequest,
    UpdateCourseResponse,
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
        return self._http.request_model(
            "POST",
            "/v1/courses",
            CreateCourseResponse,
            json=body.model_dump(mode="json", exclude_none=True),
        )

    def get(self, *, course_id: str | UUID) -> GetCourseResponse:
        """Get course details by UUID.

        Args:
            course_id: The course's unique identifier (UUID).

        Returns:
            Course details.
        """
        return self._http.request_model(
            "GET",
            f"/v1/courses/{course_id}",
            GetCourseResponse,
        )

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
        return self._http.request_model(
            "PATCH",
            f"/v1/courses/{course_id}",
            UpdateCourseResponse,
            json=body.model_dump(mode="json", exclude_unset=True),
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
        return self._http.request_model(
            "POST",
            f"/v1/courses/{course_id}/versions",
            CreateCourseVersionUploadSessionResponse,
            json=body.model_dump(mode="json", exclude_none=True),
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
        return self._http.request_model(
            "GET",
            f"/v1/courses/{course_id}/versions/{version_id}",
            GetCourseVersionResponse,
        )

"""Courses resource — course creation and management."""

from __future__ import annotations

from typing import Any

from logion._http import HttpClient
from logion.v1._types.generated.v1 import (
    CreateCourseRequest,
    CreateCourseResponse,
    CreateCourseVersionUploadSessionRequest,
    CreateCourseVersionUploadSessionResponse,
    GetCourseResponse,
    GetCourseVersionResponse,
    UpdateCourseRequest,
    UpdateCourseResponse,
)


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
        visibility: str | None = None,
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
            language=language,
            currency=currency,
            short_summary=short_summary,
            visibility=visibility,
        )
        return self._http.request_model(
            "POST",
            "/v1/courses",
            CreateCourseResponse,
            json=body.model_dump(mode="json", exclude_none=True),
        )

    def get(self, *, course_id: str) -> GetCourseResponse:
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
        course_id: str,
        title: str | None = ...,
        description: str | None = ...,
        price_cents: int | None = ...,
        tags: list[str] | None = ...,
        currency: str | None = ...,
        language: str | None = ...,
        short_summary: str | None = ...,
        visibility: str | None = ...,
    ) -> UpdateCourseResponse:
        """Update an existing course.

        Use ``None`` to set a field to null (clear it), or omit
        the parameter (leave as default) to keep the existing value.

        Args:
            course_id: The course's unique identifier.
            title: New title.
            description: New description.
            price_cents: New price in cents.
            tags: New tag list.
            currency: Currency code.
            language: Language code.
            short_summary: Short summary.
            visibility: Visibility setting.

        Returns:
            Updated course details.
        """
        body = UpdateCourseRequest(
            title=title if title is not ... else None,
            description=(description if description is not ... else None),
            price_cents=(price_cents if price_cents is not ... else None),
            tags=tags if tags is not ... else None,
            currency=currency if currency is not ... else None,
            language=language if language is not ... else None,
            short_summary=(
                short_summary if short_summary is not ... else None
            ),
            visibility=(visibility if visibility is not ... else None),
        )
        return self._http.request_model(
            "PATCH",
            f"/v1/courses/{course_id}",
            UpdateCourseResponse,
            json=body.model_dump(mode="json", exclude_unset=True),
        )

    def create_upload_session(
        self,
        *,
        course_id: str,
        files: list[dict[str, Any]],
    ) -> CreateCourseVersionUploadSessionResponse:
        """Create a new course version upload session.

        Args:
            course_id: The course to create a version for.
            files: List of file metadata dicts (required).

        Returns:
            Upload session details including presigned URL.
        """
        body = CreateCourseVersionUploadSessionRequest(
            files=files,
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
        course_id: str,
        version_id: str,
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

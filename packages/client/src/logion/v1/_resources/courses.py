"""Courses resource — course creation and management."""

from __future__ import annotations

from typing import Any

from logion._http import HttpClient


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
    ) -> dict[str, Any]:
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
        body: dict[str, Any] = {
            "title": title,
            "slug": slug,
        }
        if description is not None:
            body["description"] = description
        if price_cents is not None:
            body["price_cents"] = price_cents
        if tags is not None:
            body["tags"] = tags
        if language is not None:
            body["language"] = language
        if currency is not None:
            body["currency"] = currency
        if short_summary is not None:
            body["short_summary"] = short_summary
        if visibility is not None:
            body["visibility"] = visibility
        return self._http.request("POST", "/v1/courses", json=body)

    def get(self, *, course_id: str) -> dict[str, Any]:
        """Get course details by UUID.

        Args:
            course_id: The course's unique identifier (UUID).

        Returns:
            Course details.
        """
        return self._http.request("GET", f"/v1/courses/{course_id}")

    def update(
        self,
        *,
        course_id: str,
        title: str | None = None,
        description: str | None = None,
        price_cents: int | None = None,
        tags: list[str] | None = None,
        currency: str | None = None,
        language: str | None = None,
        short_summary: str | None = None,
        visibility: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing course.

        Args:
            course_id: The course's unique identifier.
            title: New title (optional).
            description: New description (optional).
            price_cents: New price in cents (optional).
            tags: New tag list (optional).
            currency: Currency code (optional).
            language: Language code (optional).
            short_summary: Short summary (optional).
            visibility: Visibility setting (optional).

        Returns:
            Updated course details.
        """
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if description is not None:
            body["description"] = description
        if price_cents is not None:
            body["price_cents"] = price_cents
        if tags is not None:
            body["tags"] = tags
        if currency is not None:
            body["currency"] = currency
        if language is not None:
            body["language"] = language
        if short_summary is not None:
            body["short_summary"] = short_summary
        if visibility is not None:
            body["visibility"] = visibility
        return self._http.request(
            "PATCH",
            f"/v1/courses/{course_id}",
            json=body,
        )

    def create_upload_session(
        self,
        *,
        course_id: str,
        files: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create a new course version upload session.

        Args:
            course_id: The course to create a version for.
            files: List of file metadata dicts (required).

        Returns:
            Upload session details including presigned URL.
        """
        body: dict[str, Any] = {
            "files": files,
        }
        return self._http.request(
            "POST",
            f"/v1/courses/{course_id}/versions",
            json=body,
        )

    def get_version(
        self,
        *,
        course_id: str,
        version_id: str,
    ) -> dict[str, Any]:
        """Get a specific course version.

        Args:
            course_id: The course identifier (UUID).
            version_id: The version identifier (UUID).

        Returns:
            Version details.
        """
        return self._http.request(
            "GET",
            f"/v1/courses/{course_id}/versions/{version_id}",
        )

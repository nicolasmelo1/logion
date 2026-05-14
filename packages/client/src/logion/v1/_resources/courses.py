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
        description: str,
        price_cents: int,
        tags: list[str] | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Create a new course.

        Args:
            title: Course title.
            description: Course description.
            price_cents: Price in cents.
            tags: Optional list of tags.
            language: Optional language code.

        Returns:
            Created course details.
        """
        body: dict[str, Any] = {
            "title": title,
            "description": description,
            "price_cents": price_cents,
        }
        if tags is not None:
            body["tags"] = tags
        if language is not None:
            body["language"] = language
        return self._http.request("POST", "/v1/courses", json=body)

    def get(self, *, course_id: str) -> dict[str, Any]:
        """Get course details.

        Args:
            course_id: The course's unique identifier.

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
    ) -> dict[str, Any]:
        """Update an existing course.

        Args:
            course_id: The course's unique identifier.
            title: New title (optional).
            description: New description (optional).
            price_cents: New price in cents (optional).
            tags: New tag list (optional).

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
        return self._http.request(
            "PATCH",
            f"/v1/courses/{course_id}",
            json=body,
        )

    def create_upload_session(
        self,
        *,
        course_id: str,
        version_label: str | None = None,
    ) -> dict[str, Any]:
        """Create a new course version upload session.

        Args:
            course_id: The course to create a version for.
            version_label: Optional version label.

        Returns:
            Upload session details including presigned URL.
        """
        body: dict[str, Any] = {}
        if version_label is not None:
            body["version_label"] = version_label
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
            course_id: The course identifier.
            version_id: The version identifier.

        Returns:
            Version details.
        """
        return self._http.request(
            "GET",
            f"/v1/courses/{course_id}/versions/{version_id}",
        )

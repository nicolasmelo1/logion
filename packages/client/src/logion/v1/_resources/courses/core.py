# SPDX-License-Identifier: MIT
"""Core course lifecycle methods."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    CompleteCourseVersionUploadSessionResponse,
    CreateCourseRequest,
    CreateCourseResponse,
    CreateCourseVersionUploadSessionRequest,
    CreateCourseVersionUploadSessionResponse,
    FileUploadRequest,
    GetCourseResponse,
    GetCourseVersionResponse,
    ListMyCoursesResponse,
    PurchaseCourseRequest,
    PurchaseCourseResponse,
    UpdateCourseRequest,
    UpdateCourseResponse,
)

from .shared import (
    SENTINEL,
    Visibility,
    _CoursesResourceBase,
    normalize_language,
    normalize_short_summary,
)


class _CoursesCoreMixin(_CoursesResourceBase):
    def create(
        self,
        *,
        title: str,
        slug: str,
        description: str | None = None,
        price_cents: int | None = None,
        tags: list[str] | None = None,
        category: str | None = None,
        language: str | None = None,
        currency: str | None = None,
        short_summary: str | None = None,
        visibility: Visibility | None = None,
    ) -> CreateCourseResponse:
        """Create a new course."""
        body = CreateCourseRequest(
            title=title,
            slug=slug,
            description=description,
            price_cents=price_cents,
            tags=tags,
            category=category,
            language=normalize_language(language),
            currency=currency,
            short_summary=normalize_short_summary(short_summary),
            visibility=visibility,
        )
        return operations.create_course(self._http, body=body)

    def get(self, *, course_id: str | UUID) -> GetCourseResponse:
        """Get course details by UUID."""
        return operations.get_course(self._http, course_id=course_id)

    def mine(
        self,
        *,
        status: str | None = None,
        visibility: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListMyCoursesResponse:
        """List the authenticated agent's own courses.

        Owner-scoped and agnostic to status and visibility, so drafts,
        private, and unlisted courses are all returned.  Optional
        ``status`` / ``visibility`` narrow the result.
        """
        return operations.list_my_courses(
            self._http,
            status=status,
            visibility=visibility,
            limit=limit,
            cursor=cursor,
        )

    def update(
        self,
        *,
        course_id: str | UUID,
        title: str | None = SENTINEL,  # type: ignore[assignment]
        description: str | None = SENTINEL,  # type: ignore[assignment]
        price_cents: int | None = SENTINEL,  # type: ignore[assignment]
        tags: list[str] | None = SENTINEL,  # type: ignore[assignment]
        category: str | None = SENTINEL,  # type: ignore[assignment]
        currency: str | None = SENTINEL,  # type: ignore[assignment]
        language: str | None = SENTINEL,  # type: ignore[assignment]
        short_summary: str | None = SENTINEL,  # type: ignore[assignment]
        visibility: Visibility | None = SENTINEL,  # type: ignore[assignment]
    ) -> UpdateCourseResponse:
        """Update an existing course."""
        fields: dict[str, Any] = {}
        if title is not SENTINEL:
            fields["title"] = title
        if description is not SENTINEL:
            fields["description"] = description
        if price_cents is not SENTINEL:
            fields["price_cents"] = price_cents
        if tags is not SENTINEL:
            fields["tags"] = tags
        if category is not SENTINEL:
            fields["category"] = category
        if currency is not SENTINEL:
            fields["currency"] = currency
        if language is not SENTINEL:
            fields["language"] = normalize_language(language)
        if short_summary is not SENTINEL:
            fields["short_summary"] = normalize_short_summary(short_summary)
        if visibility is not SENTINEL:
            fields["visibility"] = visibility
        # Validate so raw scalars coerce into their RootModel wrappers
        # (str -> Title, int -> PriceCents); model_construct would skip
        # this and trip Pydantic's serializer warning on model_dump.
        body = UpdateCourseRequest.model_validate(fields)
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
        """Create a new course version upload session."""
        typed_files = [FileUploadRequest(**entry) for entry in files]
        body = CreateCourseVersionUploadSessionRequest(files=typed_files)
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
        """Get a specific course version."""
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
        """Complete an upload session for a course version."""
        return operations.complete_upload_session(
            self._http,
            course_id=course_id,
            version_id=version_id,
        )

    def purchase(
        self,
        *,
        course_id: str | UUID,
        expected_price_cents: int | None = None,
        idempotency_key: str | None = None,
    ) -> PurchaseCourseResponse:
        """Purchase a course using credits.

        Args:
            course_id: The course to purchase.
            expected_price_cents: Optional price guard to reject
                if the price changed since the caller last checked.
            idempotency_key: Optional idempotency key for safe
                retries.

        Returns:
            Purchase result with order, balance change, and
            entitlement status.
        """
        body = PurchaseCourseRequest(
            expected_price_cents=expected_price_cents,
            idempotency_key=idempotency_key,
        )
        return operations.purchase_course(
            self._http,
            course_id=course_id,
            body=body,
        )

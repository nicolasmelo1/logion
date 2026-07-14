# SPDX-License-Identifier: MIT
"""Course source-link resource methods."""

from __future__ import annotations

from uuid import UUID

from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    GetCourseSourceLinkResponse,
    PackageMapPath,
    SetCourseSourceLinkRequest,
    SetCourseSourceLinkResponse,
)

from .shared import _CoursesResourceBase


class _CoursesSourceLinkMixin(_CoursesResourceBase):
    def set_source_link(
        self,
        *,
        course_id: str | UUID,
        repository: str,
        ref: str = "main",
        package_map_path: str | None = None,
    ) -> SetCourseSourceLinkResponse:
        """Set or update the GitHub source link for a course."""
        body = SetCourseSourceLinkRequest(
            repository=repository,
            ref=ref,
            package_map_path=(
                PackageMapPath(root=package_map_path)
                if package_map_path is not None
                else None
            ),
        )
        return operations.set_course_source_link(
            self._http,
            course_id=course_id,
            body=body,
        )

    def get_source_link(
        self,
        *,
        course_id: str | UUID,
    ) -> GetCourseSourceLinkResponse:
        """Get the source link for a course."""
        return operations.get_course_source_link(
            self._http,
            course_id=course_id,
        )

    def delete_source_link(
        self,
        *,
        course_id: str | UUID,
    ) -> None:
        """Revoke the source link for a course (idempotent)."""
        operations.delete_course_source_link(
            self._http,
            course_id=course_id,
        )

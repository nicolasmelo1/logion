"""Courses resource package."""

from __future__ import annotations

from logion._http import HttpClient

from .core import _CoursesCoreMixin
from .publication import _CoursesPublicationMixin
from .reviews import _CoursesReviewsMixin


class CoursesResource(
    _CoursesCoreMixin,
    _CoursesReviewsMixin,
    _CoursesPublicationMixin,
):
    """Manage courses in the Logion marketplace."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http


__all__ = ["CoursesResource"]

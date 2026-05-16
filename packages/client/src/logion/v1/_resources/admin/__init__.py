"""Admin resource package."""

from __future__ import annotations

from logion._http import HttpClient

from .courses import _AdminCoursesMixin
from .reports import _AdminReportsMixin
from .users_agents import _AdminUsersAgentsMixin


class AdminResource(
    _AdminCoursesMixin,
    _AdminUsersAgentsMixin,
    _AdminReportsMixin,
):
    """Admin endpoints for moderation and user management."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http


__all__ = ["AdminResource"]

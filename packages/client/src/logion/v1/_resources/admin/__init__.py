# SPDX-License-Identifier: MIT
"""Admin resource package."""

from __future__ import annotations

from logion._http import HttpClient

from .courses import _AdminCoursesMixin
from .payments import _AdminPaymentsMixin
from .reports import _AdminReportsMixin
from .users_agents import _AdminUsersAgentsMixin


class AdminResource(
    _AdminCoursesMixin,
    _AdminUsersAgentsMixin,
    _AdminReportsMixin,
    _AdminPaymentsMixin,
):
    """Admin endpoints for moderation, user management, and payments."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http


__all__ = ["AdminResource"]

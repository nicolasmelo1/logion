# SPDX-License-Identifier: MIT
"""Referrals resource — codes, links, stats, and attributions."""

from __future__ import annotations

from uuid import UUID

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    GetReferralCodeResponse,
    GetReferralLinkResponse,
    GetReferralStatsResponse,
    ListReferralAttributionsResponse,
)


class ReferralsResource:
    """Manage referral codes, links, statistics, and attributions."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get_code(self) -> GetReferralCodeResponse:
        """Get the authenticated user's default referral code."""
        return operations.get_referral_code(self._http)

    def get_link(self, *, course_id: str | UUID) -> GetReferralLinkResponse:
        """Generate a referral link for a specific course."""
        return operations.get_referral_link(self._http, course_id=course_id)

    def get_stats(self) -> GetReferralStatsResponse:
        """Get referral statistics for the authenticated user."""
        return operations.get_referral_stats(self._http)

    def list_attributions(self) -> list[ListReferralAttributionsResponse]:
        """List referral attributions for the authenticated user."""
        return operations.list_referral_attributions(self._http)

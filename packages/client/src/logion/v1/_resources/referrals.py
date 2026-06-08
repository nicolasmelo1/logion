# SPDX-License-Identifier: MIT
"""Referrals resource — codes, links, stats, and attributions."""

from __future__ import annotations

from uuid import UUID

from logion._http import HttpClient


class ReferralsResource:
    """Manage referral codes, links, statistics, and attributions."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get_code(self) -> dict:
        """Get the authenticated user's default referral code.

        TODO: Wire to operations.get_referral_code after OpenAPI
        regeneration.
        """
        raise NotImplementedError(
            "Referral API operations not yet available — "
            "update the SDK after the backend contract is updated."
        )

    def get_link(self, *, course_id: str | UUID) -> dict:
        """Generate a referral link for a specific course.

        TODO: Wire to operations.get_referral_link after OpenAPI
        regeneration.
        """
        raise NotImplementedError(
            "Referral API operations not yet available — "
            "update the SDK after the backend contract is updated."
        )

    def get_stats(self) -> dict:
        """Get referral statistics for the authenticated user.

        TODO: Wire to operations.get_referral_stats after OpenAPI
        regeneration.
        """
        raise NotImplementedError(
            "Referral API operations not yet available — "
            "update the SDK after the backend contract is updated."
        )

    def list_attributions(self) -> list[dict]:
        """List referral attributions for the authenticated user.

        TODO: Wire to operations.list_referral_attributions after
        OpenAPI regeneration.
        """
        raise NotImplementedError(
            "Referral API operations not yet available — "
            "update the SDK after the backend contract is updated."
        )

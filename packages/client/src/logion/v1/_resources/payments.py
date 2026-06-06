# SPDX-License-Identifier: MIT
"""Payments resource — seller onboarding and order management."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    OnboardingLinkResponse,
    OrderResponse,
    SellerReadinessResponse,
)


class PaymentsResource:
    """Manage payments, seller onboarding, and order retrieval."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get_order(self, *, order_id: str) -> OrderResponse:
        """Get order details by ID.

        Args:
            order_id: The unique order identifier.

        Returns:
            Order details including status and amount.
        """
        return operations.get_order(self._http, order_id=order_id)

    def get_seller_readiness(self) -> SellerReadinessResponse:
        """Check if the authenticated user is ready to sell courses.

        Returns:
            Seller readiness status including Stripe onboarding
            state.
        """
        return operations.get_seller_readiness(self._http)

    def create_onboarding_link(self) -> OnboardingLinkResponse:
        """Create a Stripe Connect onboarding link for the seller.

        Returns:
            Onboarding link details with redirect URL.
        """
        return operations.create_onboarding_link(self._http)

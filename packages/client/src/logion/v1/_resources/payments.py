# SPDX-License-Identifier: MIT
"""Payments resource — seller onboarding, earnings, and cash-out."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    CashOutRequest,
    CashOutResponse,
    CreatorEarningsResponse,
    OnboardingLinkResponse,
    OrderResponse,
    SellerReadinessResponse,
)


class PaymentsResource:
    """Manage payments, seller onboarding, earnings, and cash-out."""

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

    def get_creator_earnings(self) -> CreatorEarningsResponse:
        """Get creator earnings summary.

        Returns:
            Earnings breakdown with accrued, pending, submitted,
            and paid amounts plus Connect readiness.
        """
        return operations.get_creator_earnings(self._http)

    def create_cash_out(
        self,
        *,
        minimum_payout_cents: int | None = None,
        dry_run: bool = False,
    ) -> CashOutResponse:
        """Request a cash-out of accrued creator earnings.

        Args:
            minimum_payout_cents: Override minimum payout threshold.
            dry_run: If True, compute result without processing.

        Returns:
            Cash-out result with status and transfer details.
        """
        body = CashOutRequest(
            minimum_payout_cents=minimum_payout_cents,
            dry_run=dry_run,
        )
        return operations.create_cash_out(self._http, body=body)

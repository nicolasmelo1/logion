"""Payments resource — checkout and order management."""

from __future__ import annotations

from uuid import UUID

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    CourseCheckoutRequest,
    CourseCheckoutResponse,
    OnboardingLinkResponse,
    OrderResponse,
    SellerReadinessResponse,
)


class PaymentsResource:
    """Manage payments, checkouts, and seller onboarding."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create_checkout(
        self,
        *,
        course_id: str | UUID,
    ) -> CourseCheckoutResponse:
        """Create a checkout session for a course purchase.

        Args:
            course_id: The course to purchase (UUID).

        Returns:
            Checkout session details including payment URL.
        """
        body = CourseCheckoutRequest(
            course_id=(
                course_id if isinstance(course_id, UUID) else UUID(course_id)
            ),
        )
        return operations.create_course_checkout(self._http, body=body)

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

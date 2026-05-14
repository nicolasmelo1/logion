"""Payments resource — checkout and order management."""

from __future__ import annotations

from typing import Any

from logion._http import HttpClient


class PaymentsResource:
    """Manage payments, checkouts, and seller onboarding."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create_checkout(
        self,
        *,
        course_id: str,
    ) -> dict[str, Any]:
        """Create a checkout session for a course purchase.

        Args:
            course_id: The course to purchase.

        Returns:
            Checkout session details including payment URL.
        """
        return self._http.request(
            "POST",
            "/v1/payments/course-checkouts",
            json={"course_id": course_id},
        )

    def get_order(self, *, order_id: str) -> dict[str, Any]:
        """Get order details by ID.

        Args:
            order_id: The unique order identifier.

        Returns:
            Order details including status and amount.
        """
        return self._http.request("GET", f"/v1/payments/orders/{order_id}")

    def get_seller_readiness(self) -> dict[str, Any]:
        """Check if the authenticated user is ready to sell courses.

        Returns:
            Seller readiness status including Stripe onboarding state.
        """
        return self._http.request("GET", "/v1/payments/seller-readiness")

    def create_onboarding_link(self) -> dict[str, Any]:
        """Create a Stripe Connect onboarding link for the seller.

        Returns:
            Onboarding link details with redirect URL.
        """
        return self._http.request(
            "POST",
            "/v1/payments/connect-onboarding-sessions",
        )

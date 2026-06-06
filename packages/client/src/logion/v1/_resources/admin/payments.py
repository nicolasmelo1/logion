# SPDX-License-Identifier: MIT
"""Admin payments resource — admin-triggered cash-out."""

from __future__ import annotations

from uuid import UUID

from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    AdminCashOutRequest,
    CashOutResponse,
)

from .shared import _AdminResourceBase


class _AdminPaymentsMixin(_AdminResourceBase):
    def create_cash_out(
        self,
        *,
        seller_user_id: str | UUID,
        minimum_payout_cents: int | None = None,
        dry_run: bool = False,
    ) -> CashOutResponse:
        """Admin-triggered cash-out for a seller.

        Args:
            seller_user_id: The seller to cash out for.
            minimum_payout_cents: Override minimum payout threshold.
            dry_run: If True, compute result without processing.

        Returns:
            Cash-out result with status and transfer details.
        """
        body = AdminCashOutRequest(
            seller_user_id=UUID(str(seller_user_id)),
            minimum_payout_cents=minimum_payout_cents,
            dry_run=dry_run,
        )
        return operations.admin_create_cash_out(self._http, body=body)

# SPDX-License-Identifier: MIT
"""Credits resource — balance, top-ups, and ledger."""

from __future__ import annotations

from uuid import UUID

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    CreateCreditTopUpRequest,
    CreateCreditTopUpResponse,
    GetCreditBalanceResponse,
    GetCreditTopUpResponse,
    ListCreditLedgerResponse,
)


class CreditsResource:
    """Manage authenticated-agent credits and top-up checkouts."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get_balance(self) -> GetCreditBalanceResponse:
        """Get the current credit balance for the authenticated user."""
        return operations.get_credit_balance(self._http)

    def create_top_up(
        self,
        *,
        amount_cents: int,
        currency: str = "usd",
    ) -> CreateCreditTopUpResponse:
        """Create a Stripe Checkout Session for a credit top-up.

        ``amount_cents`` is always in USD.  When ``currency`` differs
        from ``usd``, the backend converts the charge to the buyer's
        local currency using the current exchange rate; credits are
        still granted in USD.
        """
        body = CreateCreditTopUpRequest(amount_cents=amount_cents)
        data = body.model_dump(mode="json", exclude_none=True)
        data["currency"] = currency
        return self._http.request_model(
            "POST",
            "/v1/credits/top-ups",
            CreateCreditTopUpResponse,
            json=data,
        )

    def get_top_up(self, *, top_up_id: str | UUID) -> GetCreditTopUpResponse:
        """Get a credit top-up by ID."""
        return operations.get_credit_top_up(self._http, top_up_id=top_up_id)

    def list_ledger(self) -> list[ListCreditLedgerResponse]:
        """List credit ledger entries for the authenticated user."""
        return operations.list_credit_ledger(self._http)

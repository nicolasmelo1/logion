# SPDX-License-Identifier: MIT
"""Credits resource — balance, packs, top-ups, and ledger."""

from __future__ import annotations

from uuid import UUID

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    CreateCreditTopUpRequest,
    CreditBalanceResponse,
    CreditLedgerEntryResponse,
    CreditPackResponse,
    CreditTopUpResponse,
)


class CreditsResource:
    """Manage authenticated-agent credits and top-up checkouts."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get_balance(self) -> CreditBalanceResponse:
        """Get the current credit balance for the authenticated user."""
        return operations.get_credit_balance(self._http)

    def list_packs(self) -> list[CreditPackResponse]:
        """List server-defined credit top-up packs."""
        return operations.list_credit_packs(self._http)

    def create_top_up(self, *, pack_code: str) -> CreditTopUpResponse:
        """Create a Stripe Checkout Session for a credit top-up."""
        body = CreateCreditTopUpRequest(pack_code=pack_code)
        return operations.create_credit_top_up(self._http, body=body)

    def get_top_up(self, *, top_up_id: str | UUID) -> CreditTopUpResponse:
        """Get a credit top-up by ID."""
        return operations.get_credit_top_up(self._http, top_up_id=top_up_id)

    def list_ledger(self) -> list[CreditLedgerEntryResponse]:
        """List credit ledger entries for the authenticated user."""
        return operations.list_credit_ledger(self._http)

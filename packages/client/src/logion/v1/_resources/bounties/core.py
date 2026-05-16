"""Core bounty methods."""

from __future__ import annotations

import builtins
from datetime import datetime
from uuid import UUID

from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    CancelBountyResponse,
    CreateBountyPayoutResponse,
    CreateBountyRequest,
    CreateBountyResponse,
    FundBountyResponse,
    GetBountyResponse,
    ListBountiesResponse,
    OpenBountyResponse,
)

from .shared import VALID_SCOPE_VALUES, _BountyResourceBase


class _BountyCoreMixin(_BountyResourceBase):
    def create(
        self,
        *,
        course_id: str | UUID,
        title: str,
        description: str,
        reward_amount_cents: int,
        currency: str | None = None,
        submission_deadline: datetime | None = None,
    ) -> CreateBountyResponse:
        """Create a new bounty."""
        body = CreateBountyRequest(
            course_id=(
                course_id if isinstance(course_id, UUID) else UUID(course_id)
            ),
            title=title,
            description=description,
            reward_amount_cents=reward_amount_cents,
            currency=currency,
            submission_deadline=submission_deadline,
        )
        return operations.create_bounty(self._http, body=body)

    def list(
        self,
        *,
        scope: str | None = None,
    ) -> builtins.list[ListBountiesResponse]:
        """List bounties with optional scope filter."""
        if scope is not None and scope not in VALID_SCOPE_VALUES:
            valid = ", ".join(VALID_SCOPE_VALUES)
            msg = f"Invalid scope value {scope!r}. Must be one of: {valid}"
            raise ValueError(msg)
        return operations.list_bounties(self._http, scope=scope)

    def get(
        self,
        bounty_id: str | UUID,
    ) -> GetBountyResponse:
        """Get bounty details by UUID."""
        return operations.get_bounty(self._http, bounty_id=bounty_id)

    def update_status(
        self,
        bounty_id: str | UUID,
    ) -> OpenBountyResponse:
        """Open (re-open) a bounty by updating its status."""
        return operations.open_bounty(self._http, bounty_id=bounty_id)

    def update_funding(
        self,
        bounty_id: str | UUID,
    ) -> FundBountyResponse:
        """Fund a bounty by updating its funding."""
        return operations.fund_bounty(self._http, bounty_id=bounty_id)

    def delete(
        self,
        bounty_id: str | UUID,
    ) -> CancelBountyResponse:
        """Cancel (delete) a bounty."""
        return operations.cancel_bounty(self._http, bounty_id=bounty_id)

    def create_payout(
        self,
        bounty_id: str | UUID,
    ) -> CreateBountyPayoutResponse:
        """Create a payout for a bounty."""
        return operations.create_bounty_payout(
            self._http,
            bounty_id=bounty_id,
        )

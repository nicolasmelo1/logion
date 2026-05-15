"""Bounties resource — bounty creation and management."""

from __future__ import annotations

import builtins
from datetime import datetime
from typing import Any
from uuid import UUID

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    AcceptBountySubmissionResponse,
    CancelBountyResponse,
    CreateBountyPayoutResponse,
    CreateBountyRequest,
    CreateBountyResponse,
    CreateBountySubmissionRequest,
    CreateBountySubmissionResponse,
    FundBountyResponse,
    GetBountyResponse,
    GetBountySubmissionResponse,
    ListBountiesResponse,
    ListBountySubmissionsResponse,
    OpenBountyResponse,
    RejectBountySubmissionResponse,
    WithdrawBountySubmissionResponse,
)

_VALID_SCOPE_VALUES = ("mine", "open", "funded")


class BountiesResource:
    """Manage bounties in the Logion marketplace."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

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
        """Create a new bounty.

        Args:
            course_id: The course the bounty is for (UUID).
            title: Bounty title (required).
            description: Bounty description (required).
            reward_amount_cents: Reward amount in cents (required).
            currency: Currency code (defaults to \"USD\").
            submission_deadline: ISO-8601 deadline for
                submissions.

        Returns:
            Created bounty details.
        """
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
        """List bounties with optional scope filter.

        Args:
            scope: Filter scope — one of: mine, open, funded.
                Defaults to \"mine\" on the server side.

        Returns:
            List of bounty items.

        Raises:
            ValueError: If *scope* is not a recognised value.
        """
        if scope is not None and scope not in _VALID_SCOPE_VALUES:
            valid = ", ".join(_VALID_SCOPE_VALUES)
            msg = f"Invalid scope value {scope!r}. Must be one of: {valid}"
            raise ValueError(msg)

        return operations.list_bounties(self._http, scope=scope)

    def get(
        self,
        bounty_id: str | UUID,
    ) -> GetBountyResponse:
        """Get bounty details by UUID.

        Args:
            bounty_id: The bounty's unique identifier (UUID).

        Returns:
            Bounty details.
        """
        return operations.get_bounty(self._http, bounty_id=bounty_id)

    def update_status(
        self,
        bounty_id: str | UUID,
    ) -> OpenBountyResponse:
        """Open (re-open) a bounty by updating its status.

        Args:
            bounty_id: The bounty's unique identifier (UUID).

        Returns:
            Updated bounty details.
        """
        return operations.open_bounty(self._http, bounty_id=bounty_id)

    def update_funding(
        self,
        bounty_id: str | UUID,
    ) -> FundBountyResponse:
        """Fund a bounty by updating its funding.

        Args:
            bounty_id: The bounty's unique identifier (UUID).

        Returns:
            Updated bounty details with funding info.
        """
        return operations.fund_bounty(self._http, bounty_id=bounty_id)

    def delete(
        self,
        bounty_id: str | UUID,
    ) -> CancelBountyResponse:
        """Cancel (delete) a bounty.

        Args:
            bounty_id: The bounty's unique identifier (UUID).

        Returns:
            Cancelled bounty details.
        """
        return operations.cancel_bounty(self._http, bounty_id=bounty_id)

    def create_payout(
        self,
        bounty_id: str | UUID,
    ) -> CreateBountyPayoutResponse:
        """Create a payout for a bounty.

        Args:
            bounty_id: The bounty's unique identifier (UUID).

        Returns:
            Created payout details.
        """
        return operations.create_bounty_payout(
            self._http,
            bounty_id=bounty_id,
        )

    def create_submission(
        self,
        bounty_id: str | UUID,
        *,
        title: str,
        description: str,
        evidence: dict[str, Any] | None = None,
        proposed_course_version_id: str | UUID | None = None,
    ) -> CreateBountySubmissionResponse:
        """Submit work for a bounty.

        Args:
            bounty_id: The bounty's unique identifier (UUID).
            title: Submission title (required).
            description: Submission description (required).
            evidence: Optional evidence as key-value dict.
            proposed_course_version_id: Optional course version
                UUID to link with the submission.

        Returns:
            Created submission details.
        """
        body = CreateBountySubmissionRequest(
            title=title,
            description=description,
            evidence=evidence,
            proposed_course_version_id=(
                proposed_course_version_id
                if proposed_course_version_id is None
                or isinstance(proposed_course_version_id, UUID)
                else UUID(proposed_course_version_id)
            ),
        )
        return operations.create_bounty_submission(
            self._http,
            bounty_id=bounty_id,
            body=body,
        )

    def list_submissions(
        self,
        bounty_id: str | UUID,
    ) -> builtins.list[ListBountySubmissionsResponse]:
        """List submissions for a bounty.

        Args:
            bounty_id: The bounty's unique identifier (UUID).

        Returns:
            List of submission items.
        """
        return operations.list_bounty_submissions(
            self._http,
            bounty_id=bounty_id,
        )

    def get_submission(
        self,
        bounty_id: str | UUID,
        submission_id: str | UUID,
    ) -> GetBountySubmissionResponse:
        """Get a specific submission for a bounty.

        Args:
            bounty_id: The bounty's unique identifier (UUID).
            submission_id: The submission's unique identifier
                (UUID).

        Returns:
            Submission details.
        """
        return operations.get_bounty_submission(
            self._http,
            bounty_id=bounty_id,
            submission_id=submission_id,
        )

    def accept_submission(
        self,
        bounty_id: str | UUID,
        submission_id: str | UUID,
    ) -> AcceptBountySubmissionResponse:
        """Accept a bounty submission.

        Args:
            bounty_id: The bounty's unique identifier (UUID).
            submission_id: The submission's unique identifier
                (UUID).

        Returns:
            Accepted submission details.
        """
        return operations.accept_bounty_submission(
            self._http,
            bounty_id=bounty_id,
            submission_id=submission_id,
        )

    def reject_submission(
        self,
        bounty_id: str | UUID,
        submission_id: str | UUID,
    ) -> RejectBountySubmissionResponse:
        """Reject a bounty submission.

        Args:
            bounty_id: The bounty's unique identifier (UUID).
            submission_id: The submission's unique identifier
                (UUID).

        Returns:
            Rejected submission details.
        """
        return operations.reject_bounty_submission(
            self._http,
            bounty_id=bounty_id,
            submission_id=submission_id,
        )

    def delete_submission(
        self,
        bounty_id: str | UUID,
        submission_id: str | UUID,
    ) -> WithdrawBountySubmissionResponse:
        """Withdraw (delete) a bounty submission.

        Args:
            bounty_id: The bounty's unique identifier (UUID).
            submission_id: The submission's unique identifier
                (UUID).

        Returns:
            Withdrawn submission details.
        """
        return operations.withdraw_bounty_submission(
            self._http,
            bounty_id=bounty_id,
            submission_id=submission_id,
        )

# SPDX-License-Identifier: MIT
"""Bounty submission methods."""

from __future__ import annotations

import builtins
from typing import Any
from uuid import UUID

from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    AcceptBountySubmissionResponse,
    CreateBountySubmissionRequest,
    CreateBountySubmissionResponse,
    GetBountySubmissionResponse,
    ListBountySubmissionsResponse,
    OpenSubmissionPrResponse,
    RejectBountySubmissionResponse,
    WithdrawBountySubmissionResponse,
)

from .shared import _BountyResourceBase


class _BountySubmissionsMixin(_BountyResourceBase):
    def create_submission(
        self,
        bounty_id: str | UUID,
        *,
        title: str,
        description: str,
        evidence: dict[str, Any] | None = None,
        proposed_course_version_id: str | UUID | None = None,
        github_pr: bool | None = None,
    ) -> CreateBountySubmissionResponse:
        """Submit work for a bounty."""
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
            github_pr=github_pr,
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
        """List submissions for a bounty."""
        return operations.list_bounty_submissions(
            self._http,
            bounty_id=bounty_id,
        )

    def get_submission(
        self,
        bounty_id: str | UUID,
        submission_id: str | UUID,
    ) -> GetBountySubmissionResponse:
        """Get a specific submission for a bounty."""
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
        """Accept a bounty submission."""
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
        """Reject a bounty submission."""
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
        """Withdraw (delete) a bounty submission."""
        return operations.withdraw_bounty_submission(
            self._http,
            bounty_id=bounty_id,
            submission_id=submission_id,
        )

    def open_pr(
        self,
        bounty_id: str | UUID,
        submission_id: str | UUID,
    ) -> OpenSubmissionPrResponse:
        """Retry GitHub PR materialization for a submission (repair)."""
        return operations.open_submission_pr(
            self._http,
            bounty_id=bounty_id,
            submission_id=submission_id,
        )

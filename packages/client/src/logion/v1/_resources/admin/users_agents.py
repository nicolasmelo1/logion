# SPDX-License-Identifier: MIT
"""User and agent moderation methods for the admin resource."""

from __future__ import annotations

from uuid import UUID

from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    GetAgentDetailResponse,
    GetUserDetailResponse,
    ReactivateAgentResponse,
    ReactivateUserResponse,
    SuspendAgentResponse,
    SuspendUserResponse,
    UpdateBillingExemptionRequest,
    UpdateBillingExemptionResponse,
)

from .shared import _AdminResourceBase


class _AdminUsersAgentsMixin(_AdminResourceBase):
    def get_user(
        self,
        user_id: str | UUID,
    ) -> GetUserDetailResponse:
        """Get user detail for moderation."""
        return operations.get_user_detail(self._http, user_id=user_id)

    def update_user_billing_exemption(
        self,
        user_id: str | UUID,
        *,
        enabled: bool,
    ) -> UpdateBillingExemptionResponse:
        """Grant or revoke a user billing exemption."""
        body = UpdateBillingExemptionRequest(enabled=enabled)
        return operations.update_billing_exemption(
            self._http,
            user_id=user_id,
            body=body,
        )

    def suspend_user(
        self,
        user_id: str | UUID,
    ) -> SuspendUserResponse:
        """Suspend a user and all their active agents."""
        return operations.suspend_user(self._http, user_id=user_id)

    def unsuspend_user(
        self,
        user_id: str | UUID,
    ) -> ReactivateUserResponse:
        """Reactivate a suspended user and their agents."""
        return operations.reactivate_user(self._http, user_id=user_id)

    def get_agent(
        self,
        agent_id: str | UUID,
    ) -> GetAgentDetailResponse:
        """Get agent detail for moderation."""
        return operations.get_agent_detail(self._http, agent_id=agent_id)

    def suspend_agent(
        self,
        agent_id: str | UUID,
    ) -> SuspendAgentResponse:
        """Suspend an agent."""
        return operations.suspend_agent(self._http, agent_id=agent_id)

    def unsuspend_agent(
        self,
        agent_id: str | UUID,
    ) -> ReactivateAgentResponse:
        """Reactivate a suspended agent."""
        return operations.reactivate_agent(self._http, agent_id=agent_id)

# SPDX-License-Identifier: MIT
"""GitHub setup methods for the landing companion flow."""

from __future__ import annotations

from typing import Any

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    ClaimSetupHandoffRequest,
    ClaimSetupHandoffResponse,
    RedeemSetupTokenRequest,
    RedeemSetupTokenResponse,
)


class GithubSetupResource:
    """Landing companion GitHub App setup endpoints."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def start(self) -> dict[str, Any]:
        """Begin the landing-page GitHub App setup flow."""
        return operations.setup_github_start(self._http)

    def callback(
        self,
        *,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Handle the landing-page GitHub App setup callback."""
        return operations.setup_github_callback(
            self._http,
            code=code,
            state=state,
            error=error,
        )

    def claim_handoff(
        self,
        *,
        handoff_id: str,
    ) -> ClaimSetupHandoffResponse:
        """Claim a setup handoff token after GitHub App installation."""
        body = ClaimSetupHandoffRequest(handoff_id=handoff_id)
        return operations.claim_setup_handoff(self._http, body=body)

    def redeem_token(
        self,
        *,
        setup_token: str,
        agent_name: str,
        agent_description: str | None = None,
    ) -> RedeemSetupTokenResponse:
        """Redeem a setup token to finish onboarding."""
        body = RedeemSetupTokenRequest(
            setup_token=setup_token,
            agent_name=agent_name,
            agent_description=agent_description,
        )
        return operations.redeem_setup_token(self._http, body=body)

    def get_token_status(
        self,
        *,
        prefix: str,
    ) -> dict[str, str]:
        """Check whether a setup-token prefix is still pending."""
        return operations.get_setup_token_status(
            self._http,
            prefix=prefix,
        )

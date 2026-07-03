# SPDX-License-Identifier: MIT
"""Identity resource — user and agent onboarding."""

from __future__ import annotations

from typing import Any, cast

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    AddAgentToUserRequest,
    AddAgentToUserResponse,
    AuthorizeRequest,
    AuthorizeResponse,
    CreateUserWithAgentRequest,
    CreateUserWithAgentResponse,
    DeviceBeginRequest,
    DeviceBeginResponse,
    DevicePollGrantedResponse,
    DevicePollPendingResponse,
    DevicePollRequest,
    GithubIdentityResponse,
    RotateAgentApiKeyRequest,
    RotateAgentApiKeyResponse,
    UserName,
)


class IdentityResource:
    """Manage users and agents in the identity service."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create_user_with_agent(
        self,
        *,
        email: str,
        user_password: str,
        agent_name: str,
        user_name: str | None = None,
        agent_description: str | None = None,
        referral_code: str | None = None,
    ) -> CreateUserWithAgentResponse:
        """Create a new user with an associated agent.

        Args:
            email: The user's email address.
            user_password: The user's password (min 8 chars).
            agent_name: Display name for the agent.
            user_name: Optional display name for the user.
            agent_description: Optional description of the agent.
            referral_code: Optional referral code for attribution.

        Returns:
            Response containing user, agent, and API key details.
        """
        body = CreateUserWithAgentRequest(
            email=email,
            user_password=user_password,
            agent_name=agent_name,
            user_name=UserName(user_name) if user_name is not None else None,
            agent_description=agent_description,
            referral_code=referral_code,
        )
        return operations.create_user_with_agent(self._http, body=body)

    def add_agent_to_user(
        self,
        *,
        user_id: str,
        agent_name: str,
        user_password: str,
        agent_description: str | None = None,
    ) -> AddAgentToUserResponse:
        """Add a new agent to an existing user.

        Args:
            user_id: The user's unique identifier.
            agent_name: Display name for the agent.
            user_password: The user's password for verification.
            agent_description: Optional description of the agent.

        Returns:
            Response with agent details and API key.
        """
        body = AddAgentToUserRequest(
            agent_name=agent_name,
            user_password=user_password,
            agent_description=agent_description,
        )
        return operations.add_agent_to_user(
            self._http,
            user_id=user_id,
            body=body,
        )

    def rotate_api_key(
        self,
        *,
        user_id: str,
        agent_id: str,
        user_password: str,
    ) -> RotateAgentApiKeyResponse:
        """Rotate the API key for an existing agent.

        Args:
            user_id: The user's unique identifier.
            agent_id: The agent whose key to rotate.
            user_password: The user's password for verification.

        Returns:
            Response with the new API key.
        """
        body = RotateAgentApiKeyRequest(
            user_password=user_password,
        )
        return operations.rotate_agent_api_key(
            self._http,
            user_id=user_id,
            agent_id=agent_id,
            body=body,
        )

    def begin_github_authorization(
        self,
        *,
        scope_tier: str = "identity",
        redirect_target: str = "none",
    ) -> AuthorizeResponse:
        """Begin the GitHub OAuth authorization flow.

        Args:
            scope_tier: OAuth scope tier — ``identity`` or ``repo``.
            redirect_target: Where to redirect after authorization.

        Returns:
            Response containing the authorize URL and state expiry.
        """
        body = AuthorizeRequest(
            scope_tier=scope_tier,
            redirect_target=redirect_target,
        )
        return operations.begin_github_authorization(self._http, body=body)

    def complete_github_callback(
        self,
        *,
        code: str,
        state: str,
    ) -> str:
        """Complete the GitHub OAuth callback (GET with query params).

        Args:
            code: Authorization code from GitHub.
            state: State token from the authorization request.

        Returns:
            HTML body or plain-text response from the callback endpoint.
        """
        return cast(
            str,
            self._http.request(
                "GET",
                "/v1/identity/github/callback",
                params={"code": code, "state": state},
            ),
        )

    def begin_github_device_flow(
        self,
        *,
        scope_tier: str = "identity",
    ) -> DeviceBeginResponse:
        """Begin the GitHub device flow authorization.

        Args:
            scope_tier: OAuth scope tier — ``identity`` or ``repo``.

        Returns:
            Response with device code, user code, and verification URI.
        """
        body = DeviceBeginRequest(scope_tier=scope_tier)
        return operations.begin_github_device_flow(self._http, body=body)

    def poll_github_device_flow(
        self,
        *,
        device_code: str,
        scope_tier: str = "identity",
    ) -> DevicePollGrantedResponse | DevicePollPendingResponse:
        """Poll the GitHub device flow for authorization status.

        Returns ``DevicePollPendingResponse`` while the user has not yet
        completed authorization, and ``DevicePollGrantedResponse`` once
        they have.

        Args:
            device_code: Device code from the begin response.
            scope_tier: OAuth scope tier — ``identity`` or ``repo``.

        Returns:
            Granted or pending response depending on authorization state.
        """
        body = DevicePollRequest(
            device_code=device_code,
            scope_tier=scope_tier,
        )
        data = cast(
            dict[str, Any],
            self._http.request(
                "POST",
                "/v1/identity/github/device/poll",
                json=body.model_dump(mode="json", exclude_none=True),
            ),
        )
        if data.get("status") == "pending" or "github_login" not in data:
            return DevicePollPendingResponse.model_validate(data)
        return DevicePollGrantedResponse.model_validate(data)

    def get_github_identity(self) -> GithubIdentityResponse:
        """Get the current GitHub identity connection status.

        Returns:
            Response with connection status, login, and scope tier.
        """
        return operations.get_github_identity(self._http)

    def revoke_github_identity(self) -> dict[str, object]:
        """Revoke the GitHub identity connection.

        Returns:
            Raw response dict from the revoke endpoint.
        """
        return operations.revoke_github_identity(self._http)

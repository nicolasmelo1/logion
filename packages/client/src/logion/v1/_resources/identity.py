"""Identity resource — user and agent onboarding."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._types.generated.v1 import (
    AddAgentToUserRequest,
    AddAgentToUserResponse,
    CreateUserWithAgentRequest,
    CreateUserWithAgentResponse,
    RotateAgentApiKeyRequest,
    RotateAgentApiKeyResponse,
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
    ) -> CreateUserWithAgentResponse:
        """Create a new user with an associated agent.

        Args:
            email: The user's email address.
            user_password: The user's password (min 8 chars).
            agent_name: Display name for the agent.
            user_name: Optional display name for the user.
            agent_description: Optional description of the agent.

        Returns:
            Response containing user, agent, and API key details.
        """
        body = CreateUserWithAgentRequest(
            email=email,
            user_password=user_password,
            agent_name=agent_name,
            user_name=user_name,
            agent_description=agent_description,
        )
        return self._http.request_model(
            "POST",
            "/v1/identity/users",
            CreateUserWithAgentResponse,
            json=body.model_dump(exclude_none=True),
        )

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
        return self._http.request_model(
            "POST",
            f"/v1/identity/users/{user_id}/agents",
            AddAgentToUserResponse,
            json=body.model_dump(exclude_none=True),
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
        return self._http.request_model(
            "POST",
            f"/v1/identity/users/{user_id}/agents/{agent_id}/api-keys",
            RotateAgentApiKeyResponse,
            json=body.model_dump(exclude_none=True),
        )

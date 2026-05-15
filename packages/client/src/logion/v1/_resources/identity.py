"""Identity resource — user and agent onboarding."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import (
    AddAgentToUserRequest,
    AddAgentToUserResponse,
    CreateUserWithAgentRequest,
    CreateUserWithAgentResponse,
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
            user_name=UserName(user_name) if user_name is not None else None,
            agent_description=agent_description,
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

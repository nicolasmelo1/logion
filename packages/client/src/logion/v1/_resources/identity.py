"""Identity resource — user and agent onboarding."""

from __future__ import annotations

from typing import Any

from logion._http import HttpClient


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
    ) -> dict[str, Any]:
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
        body: dict[str, Any] = {
            "email": email,
            "user_password": user_password,
            "agent_name": agent_name,
        }
        if user_name is not None:
            body["user_name"] = user_name
        if agent_description is not None:
            body["agent_description"] = agent_description
        return self._http.request("POST", "/v1/identity/users", json=body)

    def add_agent_to_user(
        self,
        *,
        user_id: str,
        agent_name: str,
        user_password: str,
        agent_description: str | None = None,
    ) -> dict[str, Any]:
        """Add a new agent to an existing user.

        Args:
            user_id: The user's unique identifier.
            agent_name: Display name for the agent.
            user_password: The user's password for verification.
            agent_description: Optional description of the agent.

        Returns:
            Response with agent details and API key.
        """
        body: dict[str, Any] = {
            "agent_name": agent_name,
            "user_password": user_password,
        }
        if agent_description is not None:
            body["agent_description"] = agent_description
        return self._http.request(
            "POST",
            f"/v1/identity/users/{user_id}/agents",
            json=body,
        )

    def rotate_api_key(
        self,
        *,
        user_id: str,
        agent_id: str,
        user_password: str,
    ) -> dict[str, Any]:
        """Rotate the API key for an existing agent.

        Args:
            user_id: The user's unique identifier.
            agent_id: The agent whose key to rotate.
            user_password: The user's password for verification.

        Returns:
            Response with the new API key.
        """
        body: dict[str, Any] = {
            "user_password": user_password,
        }
        return self._http.request(
            "POST",
            f"/v1/identity/users/{user_id}/agents/{agent_id}/api-keys",
            json=body,
        )

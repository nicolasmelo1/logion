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
        agent_name: str,
        agent_type: str | None = None,
    ) -> dict[str, Any]:
        """Create a new user with an associated agent.

        Args:
            email: The user's email address.
            agent_name: Display name for the agent.
            agent_type: Optional agent type (e.g. "claude", "gpt").

        Returns:
            Response containing user, agent, and API key details.
        """
        body: dict[str, Any] = {
            "email": email,
            "agent_name": agent_name,
        }
        if agent_type is not None:
            body["agent_type"] = agent_type
        return self._http.request("POST", "/v1/identity/users", json=body)

    def add_agent_to_user(
        self,
        *,
        user_id: str,
        agent_name: str,
        agent_type: str | None = None,
    ) -> dict[str, Any]:
        """Add a new agent to an existing user.

        Args:
            user_id: The user's unique identifier.
            agent_name: Display name for the agent.
            agent_type: Optional agent type.

        Returns:
            Response with agent details and API key.
        """
        body: dict[str, Any] = {"agent_name": agent_name}
        if agent_type is not None:
            body["agent_type"] = agent_type
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
    ) -> dict[str, Any]:
        """Rotate the API key for an existing agent.

        Args:
            user_id: The user's unique identifier.
            agent_id: The agent whose key to rotate.

        Returns:
            Response with the new API key.
        """
        return self._http.request(
            "POST",
            f"/v1/identity/users/{user_id}/agents/{agent_id}/api-keys",
        )

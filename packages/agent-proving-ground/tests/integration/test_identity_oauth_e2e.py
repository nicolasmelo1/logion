from __future__ import annotations

import pytest

from agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
)
from agent_proving_ground.scenarios.loader import load_scenario


@pytest.mark.asyncio
async def test_github_identity_query_uses_contract_fields(monkeypatch) -> None:
    queries = LogionApiQueries(
        "http://devrig.test",
        RoleKeyStore({"seller": {"api_key": "redacted"}}),
    )

    async def fake_get(path: str, role: str | None) -> tuple[int, object]:
        assert path == "/v1/identity/github"
        assert role == "seller"
        return 200, {
            "connected": True,
            "github_login": "test-user",
            "scope_tier": "repo",
            "status": "active",
        }

    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query(
        {"type": "github_identity_linked", "identity_agent": "creator"},
        {"creator": "seller"},
    )

    assert result["connected"] is True
    assert result["github_login"] == "test-user"
    assert result["scope_tier"] == "repo"
    assert result["evidence"] == {
        "source": "api",
        "endpoint": "/v1/identity/github",
    }


def test_identity_oauth_scenario_is_local_devrig_and_observed() -> None:
    scenario = load_scenario("builtin:identity_oauth_e2e")

    assert scenario.api_adapter == "local-devrig"
    assert {agent.devrig_role for agent in scenario.agents} == {
        "seller",
        "admin",
    }
    assertion = scenario.phases[0].assertions[0]
    assert assertion.type == "api.github_identity_linked"
    assert assertion.params == {"identity_agent": "creator"}

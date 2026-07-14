from __future__ import annotations

from pathlib import Path

import pytest

from agent_proving_ground.api_adapters.github_observer import (
    BUYER_TOKEN_ENV,
    CREATOR_TOKEN_ENV,
    GithubObserver,
)
from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.github import (
    GithubInstallationDeliveredAssertion,
)
from agent_proving_ground.models import World
from agent_proving_ground.scenarios.loader import load_scenario
from agent_proving_ground.timeline import Timeline


def _context(tmp_path: Path) -> AssertionContext:
    return AssertionContext(
        scenario_name="test",
        phase_id="github",
        world=World(
            run_id="run-1",
            base_url="http://mock",
            root_dir=tmp_path,
            data={"gh_repo": "owner/repo"},
        ),
        api=MockApiAdapter(),
        artifacts_dir=tmp_path,
        timeline=Timeline(tmp_path / "timeline.jsonl"),
    )


def test_observer_rejects_unknown_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(BUYER_TOKEN_ENV, "buyer-token")

    observer = GithubObserver.from_env(role="operator", repo="owner/repo")

    assert observer is None


async def test_installation_delivery_is_unsupported_without_app_admin_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(CREATOR_TOKEN_ENV, "creator-token")

    result = await GithubInstallationDeliveredAssertion().evaluate(
        _context(tmp_path), {}
    )

    assert result.status == "unsupported"
    assert "admin access" in result.message


def test_github_scenario_api_assertions_declare_agents() -> None:
    scenario = load_scenario("builtin:github_bounty_e2e")
    assertions = {
        assertion.type: assertion.params
        for phase in scenario.phases
        for assertion in phase.assertions
        if assertion.type.startswith("api.")
    }

    assert assertions["api.source_link_exists"]["owner_agent"] == "creator"
    assert assertions["api.bounty_exists"]["creator_agent"] == "creator"
    assert (
        assertions["api.bounty_submission_pr_opened"]["creator_agent"]
        == "creator"
    )
    assert (
        assertions["api.bounty_submission_accepted"]["creator_agent"]
        == "creator"
    )
    assert (
        assertions["api.bounty_submission_rejected"]["creator_agent"]
        == "creator"
    )

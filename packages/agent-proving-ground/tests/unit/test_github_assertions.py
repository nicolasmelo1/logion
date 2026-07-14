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
    GithubPrExistsAssertion,
)
from agent_proving_ground.assertions.registry import AssertionRegistry
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


async def test_pr_exists_assertion_rejects_closed_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class ClosedPrObserver:
        def pr_exists(self, **_params: object) -> dict[str, object]:
            return {"number": 7, "state": "closed"}

    monkeypatch.setattr(
        GithubObserver,
        "from_env",
        classmethod(lambda _cls, **_params: ClosedPrObserver()),
    )

    result = await GithubPrExistsAssertion().evaluate(
        _context(tmp_path), {"marker": "logion:bounty_submission"}
    )

    assert result.status == "failed"


def test_observer_pr_exists_ignores_closed_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer = GithubObserver(token="token", repo="owner/repo")
    monkeypatch.setattr(
        observer,
        "_get_raw",
        lambda _url: [
            {
                "number": 7,
                "state": "closed",
                "body": "logion:bounty_submission",
            },
            {
                "number": 8,
                "state": "open",
                "body": "logion:bounty_submission",
            },
        ],
    )

    result = observer.pr_exists(marker="logion:bounty_submission")

    assert result is not None
    assert result["number"] == 8


def test_observer_pr_state_is_unknown_when_pr_is_inaccessible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer = GithubObserver(token="token", repo="owner/repo")
    monkeypatch.setattr(observer, "_get", lambda _path: None)

    assert observer.pr_state(7) == "unknown"


async def test_bounty_submission_pr_opened_remains_registered(
    tmp_path: Path,
) -> None:
    result = await AssertionRegistry().evaluate(
        _context(tmp_path),
        "api.bounty_submission_pr_opened",
        {"bounty": "bounty-1", "submission": "submission-1"},
    )

    assert result.status == "passed"
    assert result.evidence["submission_id"] == "submission-1"


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

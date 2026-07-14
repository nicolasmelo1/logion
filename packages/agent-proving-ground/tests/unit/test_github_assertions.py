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
    GithubIssueBotCommentMatchAssertion,
    GithubPrClosedUnmergedAssertion,
    GithubPrExistsAssertion,
    GithubPrMergedAssertion,
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


async def test_issue_comment_invalid_regex_fails_without_crashing(
    tmp_path: Path,
) -> None:
    result = await GithubIssueBotCommentMatchAssertion().evaluate(
        _context(tmp_path), {"issue": 1, "pattern": "[invalid"}
    )

    assert result.status == "failed"
    assert "Invalid regex pattern" in result.message


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


def test_observer_qualifies_and_encodes_head_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer = GithubObserver(token="token", repo="owner/repo")
    requested_urls: list[str] = []

    def fake_get(url: str) -> list[dict[str, object]]:
        requested_urls.append(url)
        return []

    monkeypatch.setattr(observer, "_get_raw", fake_get)

    assert observer.pr_exists(head_branch="feature/branch") is None
    assert "state=open" in requested_urls[0]
    assert "head=owner%3Afeature%2Fbranch" in requested_urls[0]


def test_observer_paginates_pull_requests_and_issue_comments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer = GithubObserver(token="token", repo="owner/repo")
    requested_urls: list[str] = []

    def fake_get(url: str) -> list[dict[str, object]]:
        requested_urls.append(url)
        if "pulls?" in url:
            if url.endswith("page=1"):
                return [
                    {"number": number, "state": "open", "body": ""}
                    for number in range(100)
                ]
            return [
                {
                    "number": 101,
                    "state": "open",
                    "body": "target-marker",
                }
            ]
        if url.endswith("page=1"):
            return [{"id": number} for number in range(100)]
        return [{"id": 101}]

    monkeypatch.setattr(observer, "_get_raw", fake_get)

    pr = observer.pr_exists(marker="target-marker")
    comments = observer.issue_comments(7)

    assert pr is not None
    assert pr["number"] == 101
    assert len(comments) == 101
    assert any("per_page=100&page=2" in url for url in requested_urls)


@pytest.mark.parametrize(
    "assertion",
    [GithubPrMergedAssertion(), GithubPrClosedUnmergedAssertion()],
)
async def test_pr_state_assertions_reject_invalid_numbers(
    assertion: GithubPrMergedAssertion | GithubPrClosedUnmergedAssertion,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class Observer:
        def pr_exists(self, **_params: object) -> None:
            return None

        def pr_state(self, _number: int) -> str:
            raise AssertionError("invalid PR number must not be queried")

    monkeypatch.setattr(
        GithubObserver,
        "from_env",
        classmethod(lambda _cls, **_params: Observer()),
    )

    result = await assertion.evaluate(
        _context(tmp_path), {"pr_number": "not-a-number"}
    )

    assert result.status == "failed"


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

# SPDX-License-Identifier: MIT
"""Tests for auto GitHub PR submission rendering (Phase 15.5.2)."""

from __future__ import annotations

from typing import Any

import pytest

from cli.main import main

BID = "550e8400-e29b-41d4-a716-446655440000"
SID = "660e8400-e29b-41d4-a716-446655440001"


class FakeBountiesResource:
    """Fake bounties resource for PR materialization tests."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})
        self.github_pr_response: dict[str, Any] = {
            "status": "opened",
            "pr_url": "https://github.com/owner/repo/pull/7",
            "head_branch": "logion/submission-xyz",
            "pr_body": None,
            "reason": None,
        }
        self.open_pr_response: dict[str, Any] = {
            "pr_number": 1,
            "pr_url": "https://github.com/owner/repo/pull/1",
            "fork_required": False,
            "head_branch": "logion/bounty-x",
            "pr_body": None,
        }

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create", kwargs)
        return {"id": "bounty-1", "title": kwargs.get("title", "")}

    def list(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.last_call = ("list", kwargs)
        return []

    def create_submission(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create_submission", kwargs)
        return {
            "id": "sub-1",
            "bounty_id": kwargs.get("bounty_id", ""),
            "title": kwargs.get("title", ""),
            "github_pr": dict(self.github_pr_response),
        }

    def open_pr(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("open_submission_pr", kwargs)
        return dict(self.open_pr_response)


class FakeV1Namespace:
    def __init__(self, bounties: FakeBountiesResource) -> None:
        self.bounties = bounties


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_create_submission_renders_opened_pr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """submissions create prints the PR URL when the lane opens a PR."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main(["bounties", "submissions", "create", BID, "--title", "T"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Submission created: sub-1" in out
    assert "PR opened: https://github.com/owner/repo/pull/7" in out


def test_create_submission_renders_fork_instructions_with_body(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """submissions create prints fork steps + paste-ready body if needed."""
    bounties = FakeBountiesResource()
    marker = f"<!-- logion:bounty_submission:{SID} -->"
    bounties.github_pr_response = {
        "status": "fork_required",
        "pr_url": None,
        "head_branch": "logion/submission-xyz",
        "pr_body": marker + "\nMerge alone is neither publication nor payout.",
        "reason": None,
    }
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main(["bounties", "submissions", "create", BID, "--title", "T"])
    assert code == 0
    out = capsys.readouterr().out
    assert "This repository requires a fork" in out
    assert "logion/submission-xyz" in out
    assert "Logion registers it automatically" in out
    assert marker in out
    assert "Paste-ready PR body" in out


def test_create_submission_renders_disabled_reason(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """submissions create honestly reports a disabled PR lane."""
    bounties = FakeBountiesResource()
    bounties.github_pr_response = {
        "status": "disabled",
        "pr_url": None,
        "head_branch": None,
        "pr_body": None,
        "reason": "creator_disabled",
    }
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main(["bounties", "submissions", "create", BID, "--title", "T"])
    assert code == 0
    out = capsys.readouterr().out
    assert "GitHub PR disabled: creator_disabled" in out


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--no-github-pr"], False),
        (["--github-pr"], True),
        ([], None),
    ],
)
def test_no_github_pr_flag_forwarded(
    args: list[str],
    expected: bool | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--no-github-pr / --github-pr / absent are forwarded correctly."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "create",
        BID,
        "--title",
        "T",
        *args,
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "create_submission"
    assert kwargs.get("github_pr") is expected


def test_register_pr_command_gone(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """register-pr is not a valid sub-command."""
    with pytest.raises(SystemExit) as excinfo:
        main(["bounties", "submissions", "register-pr", BID, SID, "--json"])
    assert excinfo.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_open_pr_help_says_repair(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """open-pr help describes it as a repair command."""
    with pytest.raises(SystemExit) as excinfo:
        main(["bounties", "submissions", "--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "repair" in out
    assert "open-pr" in out


def test_open_pr_fork_rendering_no_register(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """open-pr fork path no longer mentions the removed register-pr command."""
    bounties = FakeBountiesResource()
    bounties.open_pr_response = {
        "fork_required": True,
        "pr_url": None,
        "head_branch": "logion/repair-branch",
        "pr_body": "<!-- marker -->\nmerge policy note",
    }
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main(["bounties", "submissions", "open-pr", BID, SID, "--yes"])
    assert code == 0
    out = capsys.readouterr().out
    assert "This repository requires a fork" in out
    assert "logion/repair-branch" in out
    assert "Logion registers it automatically" in out
    assert "Paste-ready PR body" in out
    assert "register-pr" not in out


def test_bounty_create_no_github_prs_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties create --no-github-prs forwards accepts_github_prs=False."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "create",
        "--course-id",
        BID,
        "--title",
        "T",
        "--description",
        "D",
        "--reward-cents",
        "100",
        "--no-github-prs",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "create"
    assert kwargs["accepts_github_prs"] is False


def test_bounty_get_renders_github_pr_enabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties get prints the computed github_pr_enabled line."""
    bounties = FakeBountiesResource()

    def get(**kwargs: Any) -> dict[str, Any]:
        bounties.last_call = ("get", kwargs)
        return {"id": kwargs.get("bounty_id", ""), "github_pr_enabled": True}

    bounties.get = get  # type: ignore[method-assign]
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main(["bounties", "get", BID])
    assert code == 0
    out = capsys.readouterr().out
    assert "GitHub PRs: enabled" in out

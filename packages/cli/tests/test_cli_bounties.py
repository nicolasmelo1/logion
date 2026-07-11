# SPDX-License-Identifier: MIT
"""Tests for the bounties commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cli.main import main


class FakeBountiesResource:
    """Fake bounties resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})
        self.open_pr_response: dict[str, Any] = {
            "pr_number": 1,
            "pr_url": "https://github.com/owner/repo/pull/1",
        }

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create", kwargs)
        return {"id": "bounty-1", "title": kwargs.get("title", "")}

    def list(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.last_call = ("list", kwargs)
        return []

    def get(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get", kwargs)
        return {"id": kwargs.get("bounty_id", "")}

    def update_status(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("update_status", kwargs)
        return {"id": kwargs.get("bounty_id", "")}

    def update_funding(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("update_funding", kwargs)
        return {"id": kwargs.get("bounty_id", "")}

    def delete(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("delete", kwargs)
        return {"id": kwargs.get("bounty_id", "")}

    def create_payout(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create_payout", kwargs)
        return {"id": kwargs.get("bounty_id", "")}

    def create_submission(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create_submission", kwargs)
        return {"id": "sub-1"}

    def list_submissions(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.last_call = ("list_submissions", kwargs)
        return []

    def get_submission(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_submission", kwargs)
        return {"id": kwargs.get("submission_id", "")}

    def accept_submission(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("accept_submission", kwargs)
        return {"id": kwargs.get("submission_id", ""), "status": "accepted"}

    def reject_submission(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("reject_submission", kwargs)
        return {"id": kwargs.get("submission_id", ""), "status": "rejected"}

    def delete_submission(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("delete_submission", kwargs)
        return {"id": kwargs.get("submission_id", ""), "status": "withdrawn"}

    def open_pr(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("open_submission_pr", kwargs)
        return self.open_pr_response

    def register_pr(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("register_submission_pr", kwargs)
        return {
            "pr_number": kwargs.get("pr_number", 1),
            "pr_url": "https://github.com/owner/repo/pull/1",
        }


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


# ── Create ──────────────────────────────────────────────────────


def test_create_bounty_calls_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties create forwards args to SDK."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "create",
        "--course-id",
        "550e8400-e29b-41d4-a716-446655440000",
        "--title",
        "Fix auth bug",
        "--description",
        "Auth module crashes on login",
        "--reward-cents",
        "5000",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "create"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["title"] == "Fix auth bug"
    assert kwargs["description"] == "Auth module crashes on login"
    assert kwargs["reward_amount_cents"] == 5000
    assert "currency" not in kwargs
    assert "submission_deadline" not in kwargs
    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "Fix auth bug"


def test_create_bounty_with_optional_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties create with optional currency and submission-deadline."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "create",
        "--course-id",
        "550e8400-e29b-41d4-a716-446655440000",
        "--title",
        "Fix auth bug",
        "--description",
        "Auth module crashes on login",
        "--reward-cents",
        "5000",
        "--currency",
        "USD",
        "--submission-deadline",
        "2025-12-31T23:59:59Z",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "create"
    assert kwargs["currency"] == "USD"
    assert kwargs["submission_deadline"] is not None


# ── List ─────────────────────────────────────────────────────────


def test_list_bounties_calls_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties list forwards scope filter."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "list",
        "--scope",
        "open",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "list"
    assert kwargs["scope"] == "open"
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.bounties.list"


def test_list_bounties_default_scope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties list without --scope omits it from kwargs."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "list",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "list"
    assert "scope" not in kwargs
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.bounties.list"


# ── Get ──────────────────────────────────────────────────────────


def test_get_bounty_calls_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties get forwards bounty_id."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "get"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.bounties.get"


def test_get_bounty_invalid_uuid() -> None:
    """bounties get rejects an invalid UUID."""
    code = main(["bounties", "get", "not-a-uuid", "--json"])
    assert code == 2


# ── Lifecycle commands (open / fund / cancel / payout) ──────────


def test_open_bounty_requires_yes() -> None:
    """bounties open returns 2 without --yes."""
    code = main([
        "bounties",
        "open",
        "550e8400-e29b-41d4-a716-446655440000",
    ])
    assert code == 2


def test_open_bounty_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties open calls update_status."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "open",
        "550e8400-e29b-41d4-a716-446655440000",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "update_status"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_fund_bounty_requires_yes() -> None:
    """bounties fund returns 2 without --yes."""
    code = main([
        "bounties",
        "fund",
        "550e8400-e29b-41d4-a716-446655440000",
    ])
    assert code == 2


def test_fund_bounty_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties fund calls update_funding."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "fund",
        "550e8400-e29b-41d4-a716-446655440000",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "update_funding"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_cancel_bounty_requires_yes() -> None:
    """bounties cancel returns 2 without --yes."""
    code = main([
        "bounties",
        "cancel",
        "550e8400-e29b-41d4-a716-446655440000",
    ])
    assert code == 2


def test_cancel_bounty_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties cancel calls delete."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "cancel",
        "550e8400-e29b-41d4-a716-446655440000",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "delete"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_payout_command_removed() -> None:
    """`logion bounties payout` is gone; accept accrues the payable
    directly and the contributor uses payments cash-out."""
    # argparse raises SystemExit(2) when an unknown sub-command is supplied.
    with pytest.raises(SystemExit) as excinfo:
        main([
            "bounties",
            "payout",
            "550e8400-e29b-41d4-a716-446655440000",
            "--yes",
        ])
    assert excinfo.value.code == 2


# ── Submissions ──────────────────────────────────────────────────


def test_submissions_create_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions create forwards args to SDK."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "create",
        "550e8400-e29b-41d4-a716-446655440000",
        "--title",
        "My submission",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "create_submission"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["title"] == "My submission"
    assert "description" not in kwargs
    assert "evidence" not in kwargs
    assert "proposed_course_version_id" not in kwargs


def test_submissions_create_with_evidence_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """bounties submissions create loads --evidence-json from file."""
    evidence_file = tmp_path / "evidence.json"
    evidence_file.write_text('{"links": ["https://example.com"]}')
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "create",
        "550e8400-e29b-41d4-a716-446655440000",
        "--title",
        "My submission",
        "--evidence-json",
        str(evidence_file),
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "create_submission"
    assert kwargs["evidence"] == {"links": ["https://example.com"]}


def test_submissions_create_with_version_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions create forwards --proposed-course-version-id."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "create",
        "550e8400-e29b-41d4-a716-446655440000",
        "--title",
        "My submission",
        "--proposed-course-version-id",
        "660e8400-e29b-41d4-a716-446655440001",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "create_submission"
    assert kwargs["proposed_course_version_id"] == (
        "660e8400-e29b-41d4-a716-446655440001"
    )


def test_submissions_list_calls_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties submissions list forwards bounty_id."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "list",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "list_submissions"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.bounties.submissions.list"


def test_submissions_get_calls_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties submissions get forwards bounty_id and submission_id."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "get_submission"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["submission_id"] == "660e8400-e29b-41d4-a716-446655440001"
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.bounties.submissions.get"


def test_submissions_accept_requires_yes() -> None:
    """bounties submissions accept returns 2 without --yes."""
    code = main([
        "bounties",
        "submissions",
        "accept",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
    ])
    assert code == 2


def test_submissions_accept_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions accept calls accept_submission."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "accept",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "accept_submission"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["submission_id"] == "660e8400-e29b-41d4-a716-446655440001"


def test_submissions_reject_requires_yes() -> None:
    """bounties submissions reject returns 2 without --yes."""
    code = main([
        "bounties",
        "submissions",
        "reject",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
    ])
    assert code == 2


def test_submissions_reject_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions reject calls reject_submission."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "reject",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "reject_submission"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["submission_id"] == "660e8400-e29b-41d4-a716-446655440001"


def test_submissions_withdraw_requires_yes() -> None:
    """bounties submissions withdraw returns 2 without --yes."""
    code = main([
        "bounties",
        "submissions",
        "withdraw",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
    ])
    assert code == 2


def test_submissions_withdraw_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions withdraw calls delete_submission."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "withdraw",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "delete_submission"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["submission_id"] == "660e8400-e29b-41d4-a716-446655440001"


def test_submissions_create_evidence_missing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """bounties submissions create exits 2 on missing --evidence-json."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "create",
        "550e8400-e29b-41d4-a716-446655440000",
        "--title",
        "My submission",
        "--evidence-json",
        str(tmp_path / "nonexistent.json"),
        "--json",
    ])
    assert code == 2
    assert bounties.last_call == ("", {})


def test_submissions_create_evidence_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """bounties submissions create exits 2 on invalid --evidence-json."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{invalid json")
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "create",
        "550e8400-e29b-41d4-a716-446655440000",
        "--title",
        "My submission",
        "--evidence-json",
        str(bad_file),
        "--json",
    ])
    assert code == 2
    assert bounties.last_call == ("", {})


def test_submissions_open_pr_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions open-pr forwards ids to SDK."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "open-pr",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "open_submission_pr"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["submission_id"] == "660e8400-e29b-41d4-a716-446655440001"


def test_submissions_open_pr_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions open-pr refuses without --yes."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "open-pr",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--json",
    ])
    assert code == 2
    assert bounties.last_call == ("", {})


def test_submissions_open_pr_json_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties submissions open-pr emits the v1 JSON envelope."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "open-pr",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--yes",
        "--json",
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.bounties.submissions.open-pr"


def test_submissions_open_pr_fork_rendering(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties submissions open-pr prints fork next steps in human mode."""
    bounties = FakeBountiesResource()
    bounties.open_pr_response = {
        "fork_required": True,
        "pr_url": None,
        "head_branch": "logion/bounty-x",
    }
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "open-pr",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--yes",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "requires a fork" in out
    assert "logion/bounty-x" in out
    assert "register-pr" in out


def test_submissions_register_pr_requires_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions register-pr requires --pr-number."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    with pytest.raises(SystemExit) as excinfo:
        main([
            "bounties",
            "submissions",
            "register-pr",
            "550e8400-e29b-41d4-a716-446655440000",
            "660e8400-e29b-41d4-a716-446655440001",
            "--json",
        ])
    assert excinfo.value.code == 2


def test_submissions_register_pr_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions register-pr forwards ids and pr-number to SDK."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "register-pr",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--pr-number",
        "42",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = bounties.last_call
    assert method == "register_submission_pr"
    assert kwargs["bounty_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["submission_id"] == "660e8400-e29b-41d4-a716-446655440001"
    assert kwargs["pr_number"] == 42


def test_submissions_register_pr_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bounties submissions register-pr refuses without --yes."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "register-pr",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--pr-number",
        "42",
        "--json",
    ])
    assert code == 2
    assert bounties.last_call == ("", {})


def test_submissions_register_pr_json_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """bounties submissions register-pr emits the v1 JSON envelope."""
    bounties = FakeBountiesResource()
    fake = FakeClient(v1=FakeV1Namespace(bounties=bounties))
    _patch_client(monkeypatch, fake)
    code = main([
        "bounties",
        "submissions",
        "register-pr",
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        "--pr-number",
        "42",
        "--yes",
        "--json",
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.bounties.submissions.register-pr"

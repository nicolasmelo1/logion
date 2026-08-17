# SPDX-License-Identifier: MIT
"""Tests for feedback CLI commands."""

from __future__ import annotations

import json

import pytest

from cli._json import JsonObject
from cli.main import main


class FakeFeedbackResource:
    """Fake feedback resource for unit tests."""

    def __init__(self) -> None:
        self.last_submit: JsonObject = {}
        self.submit_result: JsonObject = {
            "feedback_id": "fb-001",
            "resource_id": "res-001",
            "version_id": "ver-001",
            "rating": 4,
        }
        self.list_result: list[JsonObject] = [
            {
                "feedback_id": "fb-001",
                "resource_id": "res-001",
                "version_id": "ver-001",
                "rating": 4,
            }
        ]
        self.summary_result: JsonObject = {
            "resource_id": "res-001",
            "total_feedback": 3,
            "average_rating": 4.2,
        }

    def submit(
        self,
        resource_id: str,
        version_id: str,
        *,
        rating: int,
        acquisition_channel: str,
        usefulness: int | None = None,
        reliability: int | None = None,
        tool_safety: int | None = None,
        token_efficiency: int | None = None,
        completed_task: bool | None = None,
        task_class: str,
        body: str | None = None,
        source_receipt_id: str | None = None,
    ) -> JsonObject:
        self.last_submit = {
            "resource_id": resource_id,
            "version_id": version_id,
            "rating": rating,
            "acquisition_channel": acquisition_channel,
            "usefulness": usefulness,
            "reliability": reliability,
            "tool_safety": tool_safety,
            "token_efficiency": token_efficiency,
            "completed_task": completed_task,
            "task_class": task_class,
            "body": body,
            "source_receipt_id": source_receipt_id,
        }
        return self.submit_result

    def list_mine(self) -> list[JsonObject]:
        return self.list_result

    def list_for_resource(self, _resource_id: str) -> list[JsonObject]:
        return self.list_result

    def get_summary(self, _resource_id: str) -> JsonObject:
        return self.summary_result


class FakeV1Namespace:
    def __init__(self, feedback: FakeFeedbackResource) -> None:
        self.resource_feedback = feedback


class FakeClient:
    def __init__(self, feedback: FakeFeedbackResource) -> None:
        self.v1 = FakeV1Namespace(feedback)
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    feedback: FakeFeedbackResource,
) -> FakeClient:
    fake = FakeClient(feedback)
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)
    return fake


RESOURCE_ID = "123e4567-e89b-12d3-a456-426614174000"
VERSION_ID = "123e4567-e89b-12d3-a456-426614174001"


def test_feedback_submit_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """feedback submit --json emits the v1 JSON envelope."""
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)

    assert (
        main([
            "feedback",
            "submit",
            RESOURCE_ID,
            VERSION_ID,
            "--rating",
            "4",
            "--usefulness",
            "5",
            "--completed-task",
            "--task-class",
            "software-development",
            "--acquisition-channel",
            "logion-marketplace",
            "--body",
            "Great resource",
            "--json",
        ])
        == 0
    )

    assert feedback.last_submit["resource_id"] == RESOURCE_ID
    assert feedback.last_submit["version_id"] == VERSION_ID
    assert feedback.last_submit["rating"] == 4
    assert feedback.last_submit["usefulness"] == 5
    assert feedback.last_submit["completed_task"] is True
    assert feedback.last_submit["task_class"] == "software-development"
    assert feedback.last_submit["body"] == "Great resource"

    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.feedback.submit"
    assert payload["data"]["feedback_id"] == "fb-001"


def test_feedback_submit_not_completed_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """feedback submit --not-completed-task sets completed_task to False."""
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)

    assert (
        main([
            "feedback",
            "submit",
            RESOURCE_ID,
            VERSION_ID,
            "--not-completed-task",
            "--rating",
            "4",
            "--task-class",
            "coding",
            "--acquisition-channel",
            "logion-marketplace",
            "--json",
        ])
        == 0
    )

    assert feedback.last_submit["completed_task"] is False


def test_feedback_list_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """feedback list --mine --json emits the v1 JSON envelope."""
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)

    assert main(["feedback", "list", "--mine", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.feedback.list"
    assert payload["data"][0]["feedback_id"] == "fb-001"


def test_feedback_summary_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """feedback summary --json emits the v1 JSON envelope."""
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)

    assert main(["feedback", "summary", RESOURCE_ID, "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.feedback.summary"
    assert payload["data"]["total_feedback"] == 3
    assert payload["data"]["average_rating"] == 4.2


def test_feedback_submit_human_readable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """feedback submit without --json prints human-readable output."""
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)

    assert (
        main([
            "feedback",
            "submit",
            RESOURCE_ID,
            VERSION_ID,
            "--rating",
            "5",
            "--task-class",
            "coding",
            "--acquisition-channel",
            "logion-marketplace",
        ])
        == 0
    )

    out = capsys.readouterr().out
    assert "feedback_id" in out


def test_feedback_list_human_readable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """feedback list without --json prints human-readable entries."""
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)

    assert main(["feedback", "list", "--mine"]) == 0

    out = capsys.readouterr().out
    assert "fb-001" in out


def test_feedback_summary_human_readable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """feedback summary without --json prints human-readable output."""
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)

    assert main(["feedback", "summary", RESOURCE_ID]) == 0

    out = capsys.readouterr().out
    assert "total_feedback" in out


def _receipt_for(channel: str) -> JsonObject:
    return {
        "schema_version": 1,
        "resource_id": RESOURCE_ID,
        "version_id": VERSION_ID,
        "resource_type": "agent_skill",
        "channel": channel,
        "harness": "codex",
        "scope_kind": "repo-root",
        "scope_id": "b" * 64,
        "installation_id": "a" * 64,
        "target_path": "/tmp/skills/helper",
        "relative_target_path": "helper",
    }


def _submit(*extra: str) -> int:
    return main([
        "feedback",
        "submit",
        RESOURCE_ID,
        VERSION_ID,
        "--rating",
        "4",
        "--task-class",
        "software-development",
        *extra,
    ])


def test_acquisition_channel_comes_from_the_local_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The link to the acquisition must be a fact, not a typed claim."""
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)
    monkeypatch.setattr(
        "cli.commands.feedback.handlers.load_receipts",
        lambda: [_receipt_for("npx_skills")],
    )

    assert _submit() == 0

    assert feedback.last_submit["acquisition_channel"] == "npx_skills"


def test_submit_without_a_receipt_asks_for_an_explicit_channel(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Rather than inventing a channel, say what is missing."""
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)
    monkeypatch.setattr("cli.commands.feedback.handlers.load_receipts", list)

    assert _submit() != 0

    assert feedback.last_submit == {}
    assert "--acquisition-channel" in capsys.readouterr().err


def test_ambiguous_channel_requires_an_explicit_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feedback = FakeFeedbackResource()
    _patch_client(monkeypatch, feedback)
    monkeypatch.setattr(
        "cli.commands.feedback.handlers.load_receipts",
        lambda: [_receipt_for("npx_skills"), _receipt_for("hugging_face")],
    )

    assert _submit() != 0
    assert feedback.last_submit == {}

    assert _submit("--acquisition-channel", "npx_skills") == 0
    assert feedback.last_submit["acquisition_channel"] == "npx_skills"


def test_repeat_submission_is_refused_until_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hook firing twice must not become two outbound reports."""
    feedback = FakeFeedbackResource()
    feedback.submit_result = {"id": "fb-777", "rating": 4}
    _patch_client(monkeypatch, feedback)
    monkeypatch.setattr(
        "cli.commands.feedback.handlers.load_receipts",
        lambda: [_receipt_for("npx_skills")],
    )

    assert _submit() == 0
    feedback.last_submit = {}

    assert _submit() != 0
    assert feedback.last_submit == {}

    assert _submit("--force") == 0
    assert feedback.last_submit["rating"] == 4

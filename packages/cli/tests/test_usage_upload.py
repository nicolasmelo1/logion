# SPDX-License-Identifier: MIT
"""Tests for the consent gate on ``logion usage upload``.

``local-only`` and ``prompt`` are privacy promises. The only way they mean
anything is if the upload path refuses to send under them.
"""

from __future__ import annotations

import json

import pytest

from cli._json import JsonObject
from cli.integrations_state import set_mode
from cli.main import main
from cli.usage.observations import make_observation, spool_observation
from cli.usage.tombstones import receipt_tombstone


class FakeUsageReceipts:
    def __init__(self) -> None:
        self.calls: list[JsonObject] = []

    def submit(
        self,
        resource_id: str,
        version_id: str,
        *,
        observation_id: str,
        task_class: str,
        acquisition_channel: str,
        consent_policy_digest: str,
        harness: str | None = None,
        outcome: str | None = None,
        observed_at: str | None = None,
        coarse_counters: dict[str, int] | None = None,
        duration_bucket: str | None = None,
        integration_version: str | None = None,
        pseudonymous_public_key: str | None = None,
        pseudonymous_signature: str | None = None,
    ) -> JsonObject:
        self.calls.append({
            "resource_id": resource_id,
            "version_id": version_id,
            "observation_id": observation_id,
            "task_class": task_class,
            "acquisition_channel": acquisition_channel,
            "consent_policy_digest": consent_policy_digest,
            "harness": harness,
            "outcome": outcome,
            "observed_at": observed_at,
            "coarse_counters": coarse_counters,
            "duration_bucket": duration_bucket,
            "integration_version": integration_version,
            "pseudonymous_public_key": pseudonymous_public_key,
            "pseudonymous_signature": pseudonymous_signature,
        })
        return {"id": f"receipt-{len(self.calls)}"}


class FakeClient:
    def __init__(self, receipts: FakeUsageReceipts) -> None:
        self.v1 = type("V1", (), {"usage_receipts": receipts})()
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def receipts(monkeypatch: pytest.MonkeyPatch) -> FakeUsageReceipts:
    fake = FakeUsageReceipts()
    monkeypatch.setattr(
        "cli._context.LogionClient", lambda **_: FakeClient(fake)
    )
    return fake


def _spool_one(harness: str = "codex") -> str:
    obs = make_observation(
        harness=harness,
        event="resource_invoked",
        resource_id="res-001",
        version_id="ver-001",
        resource_type="agent_skill",
        acquisition_channel="npx_skills",
        installation_id="a" * 64,
        scope_kind="repo-root",
        scope_id="b" * 64,
        session_hash="sess-1",
    )
    spool_observation(obs)
    return obs.observation_id


def _upload(*extra: str) -> int:
    return main([
        "usage",
        "upload",
        "--task-class",
        "software-development",
        "--json",
        *extra,
    ])


def test_local_only_never_uploads(
    receipts: FakeUsageReceipts, capsys: pytest.CaptureFixture[str]
) -> None:
    """The mode named "no upload" must produce no request."""
    set_mode("codex", "local-only")
    observation_id = _spool_one()

    assert _upload() == 0

    data = json.loads(capsys.readouterr().out)["data"]
    assert receipts.calls == []
    assert data["uploaded"] == []
    assert "upload_not_consented" in data["skipped"][0]["reason"]
    assert receipt_tombstone(observation_id) is None


def test_off_never_uploads(receipts: FakeUsageReceipts) -> None:
    set_mode("codex", "off")
    _spool_one()

    assert _upload() == 0

    assert receipts.calls == []


def test_prompt_requires_explicit_confirmation(
    receipts: FakeUsageReceipts, capsys: pytest.CaptureFixture[str]
) -> None:
    """Prompt mode asks every time; ``--yes`` is that answer."""
    set_mode("codex", "prompt")
    _spool_one()

    assert _upload() == 0
    assert receipts.calls == []
    assert (
        "requires explicit confirmation"
        in (
            json.loads(capsys.readouterr().out)["data"]["skipped"][0]["reason"]
        )
    )

    assert _upload("--yes") == 0
    assert len(receipts.calls) == 1


def test_do_not_track_blocks_upload(
    receipts: FakeUsageReceipts, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_mode("codex", "auto")
    _spool_one()
    monkeypatch.setenv("DO_NOT_TRACK", "1")

    assert _upload() == 0

    assert receipts.calls == []


def test_auto_uploads_once_and_records_a_tombstone(
    receipts: FakeUsageReceipts,
) -> None:
    """A second run must not re-send the same observation."""
    set_mode("codex", "auto")
    observation_id = _spool_one()

    assert _upload() == 0
    assert len(receipts.calls) == 1
    assert receipt_tombstone(observation_id) == "receipt-1"

    assert _upload() == 0
    assert len(receipts.calls) == 1


def test_uploaded_payload_carries_only_opaque_metadata(
    receipts: FakeUsageReceipts,
) -> None:
    """The receipt is a statement about a version, not about the work."""
    set_mode("codex", "auto")
    _spool_one()

    assert _upload() == 0

    call = receipts.calls[0]
    assert call["acquisition_channel"] == "npx_skills"
    assert call["harness"] == "codex"
    assert call["consent_policy_digest"] == "logion.consent.v1"
    forbidden = ("prompt", "path", "body", "content", "command", "session")
    for key in call:
        assert not any(word in key for word in forbidden), key


def test_anonymous_receipt_upload_signs_with_a_stable_local_subject(
    receipts: FakeUsageReceipts,
) -> None:
    set_mode("codex", "auto")
    _spool_one()

    assert _upload() == 0

    call = receipts.calls[0]
    assert isinstance(call["pseudonymous_public_key"], str)
    assert call["pseudonymous_public_key"]
    assert isinstance(call["pseudonymous_signature"], str)
    assert call["pseudonymous_signature"]

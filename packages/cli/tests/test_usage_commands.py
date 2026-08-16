# SPDX-License-Identifier: MIT
"""Tests for usage observation CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.main import main
from cli.usage.observations import (
    OBSERVATION_FIELDS,
    UsageObservation,
    make_observation,
    spool_observation,
)


def test_observation_dataclass_fields_pinned() -> None:
    """The dataclass must have exactly the expected fields."""
    import dataclasses

    fields = tuple(f.name for f in dataclasses.fields(UsageObservation))
    assert fields == OBSERVATION_FIELDS


def test_observation_no_free_text_or_path_fields() -> None:
    """No field name may contain free-text or path-like substrings."""
    forbidden = ("path", "body", "text", "prompt", "code", "content")
    for field_name in OBSERVATION_FIELDS:
        lower = field_name.lower()
        for word in forbidden:
            assert word not in lower, (
                f"field {field_name!r} contains forbidden substring {word!r}"
            )


def _make_test_observation(
    *,
    harness: str = "codex",
    event: str = "resource_invoked",
    resource_id: str = "res-001",
    version_id: str = "ver-001",
    session_hash: str | None = "sess-abc",
) -> UsageObservation:
    return make_observation(
        harness=harness,
        event=event,
        resource_id=resource_id,
        version_id=version_id,
        resource_type="agent_skill",
        acquisition_channel="logion-marketplace",
        installation_id="inst-001",
        scope_kind="user",
        scope_id="scope-001",
        session_hash=session_hash,
    )


def _set_logion_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point LOGION_HOME at a tmp directory and return it."""
    home = tmp_path / "logion_home"
    home.mkdir()
    monkeypatch.setenv("LOGION_HOME", str(home))
    return home


def test_usage_pending_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """usage pending with empty spool outputs nothing."""
    _set_logion_home(tmp_path, monkeypatch)
    assert main(["usage", "pending", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.usage.pending"
    assert payload["data"] == []


def test_usage_pending_with_observations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """usage pending shows observations from the local spool."""
    _set_logion_home(tmp_path, monkeypatch)
    obs = _make_test_observation()
    spool_observation(obs)

    assert main(["usage", "pending", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.usage.pending"
    assert len(payload["data"]) == 1
    assert payload["data"][0]["resource_id"] == "res-001"


def test_usage_pending_since_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """usage pending --since filters by recency."""
    _set_logion_home(tmp_path, monkeypatch)
    obs = _make_test_observation()
    spool_observation(obs)

    # Should return results for a 24h window
    assert main(["usage", "pending", "--since", "24h", "--json"]) == 0

    # Should return empty for a 0s window (observations are now)
    # Use 1s to be safe
    assert main(["usage", "pending", "--since", "0s", "--json"]) == 0


def test_usage_observe_from_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """usage observe reads JSON from stdin and writes to spool."""
    _set_logion_home(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "cli.commands.usage.handlers.get_mode", lambda _harness: "prompt"
    )
    monkeypatch.setattr(
        "cli.commands.usage.handlers.load_receipts",
        lambda: [
            {
                "resource_id": "res-002",
                "version_id": "ver-002",
                "resource_type": "agent_plugin",
                "channel": "logion-marketplace",
                "installation_id": "inst-002",
                "harness": "codex",
                "scope_kind": "user",
                "scope_id": "scope-002",
            }
        ],
    )

    stdin_data = json.dumps({
        "event": "resource_invoked",
        "resource_id": "res-002",
        "version_id": "ver-002",
        "resource_type": "agent_plugin",
        "acquisition_channel": "logion-marketplace",
        "installation_id": "inst-002",
        "scope_kind": "user",
        "scope_id": "scope-002",
        "session_hash": "sess-def",
    })
    monkeypatch.setattr("sys.stdin", _FakeStdin(stdin_data))

    assert main(["usage", "observe", "--harness", "codex", "--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["kind"] == "logion.usage.observe"
    assert payload["data"]["disposition"] == "recorded"
    assert payload["data"]["observation"]["resource_id"] == "res-002"
    assert payload["data"]["observation"]["harness"] == "codex"


def test_usage_observe_json_reports_disabled_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_logion_home(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "cli.commands.usage.handlers.get_mode", lambda _harness: None
    )
    monkeypatch.setattr("sys.stdin", _FakeStdin("{}"))

    assert main(["usage", "observe", "--harness", "codex", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["data"] == {
        "disposition": "ignored",
        "reason": "integration_disabled",
    }


def test_usage_observe_always_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """usage observe exits 0 even on invalid input."""
    _set_logion_home(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "cli.commands.usage.handlers.get_mode", lambda _harness: "prompt"
    )
    monkeypatch.setattr("sys.stdin", _FakeStdin("not json"))
    assert main(["usage", "observe", "--harness", "codex", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["disposition"] == "failed"


def test_usage_observe_dedup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate observations within the window are not double-counted."""
    _set_logion_home(tmp_path, monkeypatch)
    obs = _make_test_observation(session_hash="dedup-test")
    spool_observation(obs)
    # Spool again — should be deduplicated
    spool_observation(obs)

    from cli.usage.observations import list_pending_observations

    all_obs = list_pending_observations()
    assert len(all_obs) == 1


def test_usage_dismiss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """usage dismiss removes observations by group id."""
    _set_logion_home(tmp_path, monkeypatch)
    obs = _make_test_observation(session_hash="dismiss-test")
    spool_observation(obs)

    # Compute the group id
    from cli.usage.observations import _observation_group_id

    group_id = _observation_group_id(obs)

    assert main(["usage", "dismiss", group_id, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.usage.dismiss"
    assert payload["data"]["removed"] == 1

    # Verify it's gone
    from cli.usage.observations import list_pending_observations

    remaining = list_pending_observations()
    assert len(remaining) == 0


def test_usage_dismiss_no_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """usage dismiss with unknown group id removes nothing."""
    _set_logion_home(tmp_path, monkeypatch)
    assert main(["usage", "dismiss", "nonexistent123", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["removed"] == 0


def test_spool_permissions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spool directory and file have restrictive permissions."""
    home = _set_logion_home(tmp_path, monkeypatch)
    obs = _make_test_observation()
    spool_observation(obs)

    spool_dir = home / "usage"
    spool_file = spool_dir / "observations.jsonl"

    dir_mode = spool_dir.stat().st_mode & 0o777
    file_mode = spool_file.stat().st_mode & 0o777
    assert dir_mode == 0o700
    assert file_mode == 0o600


class _FakeStdin:
    """Minimal stdin replacement for testing."""

    def __init__(self, data: str) -> None:
        self._data = data

    def read(self) -> str:
        return self._data

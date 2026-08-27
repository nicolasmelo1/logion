"""Tests for the phase 15.14.1 devrig query handlers."""

from __future__ import annotations

import json
from pathlib import Path

from agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
)


def _queries() -> LogionApiQueries:
    return LogionApiQueries(
        "http://devrig.test",
        RoleKeyStore(  # pragma: allowlist secret
            {"buyer": {"api_key": "redacted"}},  # pragma: allowlist secret
        ),
    )


def _write(tmp_path: Path, payload: dict) -> str:
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(payload))
    return str(target)


async def test_role_credentials_isolated_requires_distinct_identities(
    tmp_path,
) -> None:
    queries = _queries()
    manifest = _write(
        tmp_path,
        {
            "credentials": {
                "consumer": {
                    "agent_id": "agent-a",
                    "key_works_before_reset": True,
                    "revoked_key_rejected": True,
                },
                "auditor": {
                    "agent_id": "agent-a",  # same identity: shared key
                    "key_works_after_reset": True,
                },
            }
        },
    )
    result = await queries.query(
        {"type": "role_credentials_isolated", "manifest": manifest},
        {},
    )
    assert result["isolated"] is False


async def test_role_credentials_isolated_requires_revocation(
    tmp_path,
) -> None:
    queries = _queries()
    manifest = _write(
        tmp_path,
        {
            "credentials": {
                "consumer": {
                    "agent_id": "agent-a",
                    "key_works_before_reset": True,
                    "revoked_key_rejected": False,
                },
                "auditor": {
                    "agent_id": "agent-b",
                    "key_works_after_reset": True,
                },
            }
        },
    )
    result = await queries.query(
        {"type": "role_credentials_isolated", "manifest": manifest},
        {},
    )
    assert result["isolated"] is False
    assert result["revoked_key_rejected"] is False


async def test_role_credentials_isolated_probes_auditor_live(
    monkeypatch, tmp_path
) -> None:
    queries = _queries()
    manifest = _write(
        tmp_path,
        {
            "credentials": {
                "consumer": {
                    "agent_id": "agent-a",
                    "key_works_before_reset": True,
                    "revoked_key_rejected": True,
                },
                "auditor": {
                    "agent_id": "agent-b",
                    "key_works_after_reset": True,
                },
            }
        },
    )

    async def fake_get(path: str, role: str | None):  # noqa: ARG001
        assert role == "buyer"
        return 200, {"items": []}

    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query(
        {
            "type": "role_credentials_isolated",
            "manifest": manifest,
            "auditor_role": "buyer",
        },
        {},
    )
    assert result["isolated"] is True
    assert result["auditor_still_authenticates"] is True


async def test_role_credentials_isolated_passes_on_captured_auditor_flag(
    monkeypatch, tmp_path
) -> None:
    queries = _queries()
    manifest = _write(
        tmp_path,
        {
            "credentials": {
                "consumer": {
                    "agent_id": "agent-a",
                    "key_works_before_reset": True,
                    "revoked_key_rejected": True,
                },
                "auditor": {
                    "agent_id": "agent-b",
                    "key_works_after_reset": True,
                },
            }
        },
    )

    async def failing_get(_path: str, _role: str | None):
        return 0, {"error": "unreachable"}

    monkeypatch.setattr(queries, "_get", failing_get)
    result = await queries.query(
        {
            "type": "role_credentials_isolated",
            "manifest": manifest,
        },
        {},
    )
    # The live probe could not run; the captured flag carries the proof.
    assert result["isolated"] is True
    assert result["auditor_still_authenticates"] is False


async def test_role_credentials_isolated_missing_manifest_fails_closed(
    tmp_path,
) -> None:
    queries = _queries()
    result = await queries.query(
        {
            "type": "role_credentials_isolated",
            "manifest": str(tmp_path / "absent.json"),
        },
        {},
    )
    assert result["isolated"] is False
    assert "reason" in result


async def test_state_survives_restart_requires_identical_markers(
    tmp_path,
) -> None:
    queries = _queries()
    manifest = _write(
        tmp_path,
        {
            "before_restart": {"consumer": "m1", "auditor": "m2"},
            "after_restart": {"consumer": "m1", "auditor": "m2"},
            "cross_role_visible": False,
        },
    )
    result = await queries.query(
        {"type": "state_survives_restart", "manifest": manifest},
        {},
    )
    assert result["preserved"] is True
    assert result["cross_role_visible"] is False


async def test_state_survives_restart_fails_on_state_loss(
    tmp_path,
) -> None:
    queries = _queries()
    manifest = _write(
        tmp_path,
        {
            "before_restart": {"consumer": "m1", "auditor": "m2"},
            "after_restart": {"consumer": "missing", "auditor": "m2"},
            "cross_role_visible": False,
        },
    )
    result = await queries.query(
        {"type": "state_survives_restart", "manifest": manifest},
        {},
    )
    assert result["preserved"] is False
    assert result["before_restart"] == ["auditor", "consumer"]


async def test_state_survives_restart_fails_on_cross_role_leak(
    tmp_path,
) -> None:
    queries = _queries()
    manifest = _write(
        tmp_path,
        {
            "before_restart": {"consumer": "m1", "auditor": "m2"},
            "after_restart": {"consumer": "m1", "auditor": "m2"},
            "cross_role_visible": True,
        },
    )
    result = await queries.query(
        {"type": "state_survives_restart", "manifest": manifest},
        {},
    )
    assert result["preserved"] is False
    assert result["cross_role_visible"] is True

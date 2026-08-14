from __future__ import annotations

import json
from pathlib import Path

from agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
    _contains_forbidden_observation_data,
    _load_cli_list,
)


async def test_course_exists_honors_captured_course_id(monkeypatch) -> None:
    queries = LogionApiQueries(
        "http://devrig.test",
        RoleKeyStore(  # pragma: allowlist secret
            {"seller": {"api_key": "redacted"}}
        ),
    )

    async def fake_courses(_role: str | None) -> list[dict[str, str]]:
        return [{"id": "older-course", "status": "published"}]

    monkeypatch.setattr(queries, "_my_courses", fake_courses)
    result = await queries.query(
        {
            "type": "course_exists",
            "owner_agent": "creator",
            "course": "run-course",
        },
        {"creator": "seller"},
    )

    assert result["found"] is False
    assert result["evidence"] == {"source": "api"}


async def test_setup_token_pending_requires_exact_prefix(monkeypatch) -> None:
    queries = LogionApiQueries(
        "http://devrig.test",
        RoleKeyStore(  # pragma: allowlist secret
            {"seller": {"api_key": "redacted"}}
        ),
    )

    async def fake_get(path: str, _role: str | None):
        assert path == "/v1/setup-tokens/run-prefix"
        return 200, {"token_prefix": "other-prefix", "status": "pending"}

    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries.query(
        {
            "type": "setup_token_pending",
            "owner_agent": "creator",
            "token_prefix": "run-prefix",
        },
        {"creator": "seller"},
    )

    assert result["pending"] is False


# --- Regression tests for harness scope and observation fixes ---


def test_load_cli_list_extracts_resources_from_inventory_envelope(
    tmp_path: Path,
) -> None:
    """The CLI inventory command emits a v1 envelope with data as a dict
    containing a 'resources' list — not a bare list.  _load_cli_list must
    extract the nested list."""
    payload = {
        "version": "v1",
        "kind": "logion.resources.inventory",
        "data": {
            "harness": "codex",
            "targets": [],
            "resources": [
                {"name": "acme", "scope_kind": "repo-root"},
                {"name": "other", "scope_kind": "user"},
            ],
            "count": 2,
        },
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload))
    items = _load_cli_list(str(path), "logion.resources.inventory")
    assert len(items) == 2
    assert items[0]["name"] == "acme"


def test_load_cli_list_still_accepts_bare_list(tmp_path: Path) -> None:
    """Bare-list envelopes (if any CLI command still emits one) must
    continue to work."""
    payload = {
        "version": "v1",
        "kind": "logion.resources.versions",
        "data": [{"id": "v1"}, {"id": "v2"}],
    }
    path = tmp_path / "versions.json"
    path.write_text(json.dumps(payload))
    items = _load_cli_list(str(path), "logion.resources.versions")
    assert len(items) == 2


def test_contains_forbidden_observation_data_allows_resource_version_id() -> (
    None
):
    """The sanctioned field 'resource_version_id' contains the substring
    'source' but must NOT be flagged as forbidden."""
    envelope = {
        "event": "resource.use.completed",
        "harness": "codex",
        "harness_session_id": "sess-abc123",
        "installation_id": "inst-xyz",
        "resource_version_id": "rv-001",
        "scope_kind": "repo-root",
        "scope_id": "scope-1",
        "task_class": "software-development",
        "outcome": "completed",
        "started_at": "2026-07-29T10:00:00Z",
        "finished_at": "2026-07-29T10:05:00Z",
        "integration_version": "logion.observation.v1",
    }
    assert _contains_forbidden_observation_data(envelope) is False


def test_contains_forbidden_observation_data_rejects_adhoc_prompt_field() -> (
    None
):
    """An ad-hoc 'prompt' field must still be flagged as forbidden."""
    envelope = {
        "prompt": "write me a function",
        "event": "resource.use.completed",
    }
    assert _contains_forbidden_observation_data(envelope) is True


async def test_acquire_plan_dry_run_rejects_executable_true(
    tmp_path: Path,
) -> None:
    """A dry-run plan with executable=True must fail validation."""
    queries = LogionApiQueries(
        "http://devrig.test",
        RoleKeyStore(  # pragma: allowlist secret
            {"seller": {"api_key": "redacted"}}
        ),
    )
    plan = {
        "version": "v1",
        "kind": "logion.resources.acquire",
        "data": {
            "dry_run": True,
            "scope": "repo-root",
            "targets": [{"target_path": "/tmp/.agents/skills"}],
            "executable": True,
            "permissions_required": "unknown-until-distribution-is-resolved",
        },
    }
    plan_path = tmp_path / "acquire.json"
    plan_path.write_text(json.dumps(plan))
    snapshot = {"version": "v1", "kind": "snapshot", "data": {}}
    snap_path = tmp_path / "snapshot.json"
    snap_path.write_text(json.dumps(snapshot))
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    result = await queries.query(
        {
            "type": "resource_acquire_plan_dry_run",
            "artifact": str(plan_path),
            "expected_scope": "repo-root",
            "expected_target": "/tmp/.agents/skills",
            "before_snapshot": str(snap_path),
            "snapshot_roots": [str(root_dir)],
        },
        {},
    )
    assert result["valid"] is False
    assert result.get("executable") is True

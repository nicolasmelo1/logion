# SPDX-License-Identifier: MIT
"""Tests for usage observation CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._json import JsonObject
from cli._receipts import (
    installation_id_for,
    scope_id_for_target,
)
from cli.integrations_state import set_mode
from cli.main import main
from cli.usage.observations import (
    OBSERVATION_FIELDS,
    UsageObservation,
    list_pending_observations,
    make_observation,
    observation_group_id,
    spool_observation,
)

FIXTURES = Path(__file__).parent / "fixtures" / "hook_payloads"


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_hash", "/Users/someone/secret-repo"),
        ("session_hash", "review the auth module please"),
        ("harness", "Codex On /tmp/x"),
    ],
)
def test_observation_rejects_free_text_values(field: str, value: str) -> None:
    """A path or sentence must not survive as an identifier value.

    Pinning field *names* is not enough — the spool's privacy claim only
    holds if the values are checked too.
    """
    kwargs: dict[str, str] = {"harness": "codex", "session_hash": "sess-1"}
    kwargs[field] = value
    with pytest.raises(ValueError, match=r"opaque identifier|lowercase slug"):
        _make_test_observation(**kwargs)


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


def _receipt(
    *,
    target_path: Path,
    scope_kind: str = "repo-root",
    scope_root: Path | None = None,
    resource_id: str = "res-002",
    version_id: str = "ver-002",
    harness: str = "codex",
) -> JsonObject:
    """A receipt with the opaque ids 15.9.1 defines, not a hand-made hash."""
    root = scope_root or target_path.parent
    scope_id = scope_id_for_target(scope_kind, root)
    relative = target_path.name
    return {
        "schema_version": 1,
        "resource_id": resource_id,
        "version_id": version_id,
        "resource_type": "agent_skill",
        "channel": "npx_skills",
        "harness": harness,
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "installation_id": installation_id_for(scope_id, relative),
        "target_path": str(target_path),
        "relative_target_path": relative,
    }


def _install(root: Path, name: str = "review-helper") -> Path:
    target = root / ".agents" / "skills" / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text("# helper\n", encoding="utf-8")
    return target


def _load_payload(
    name: str, *, install: Path, repo: Path, home: Path
) -> JsonObject:
    raw = (FIXTURES / name).read_text(encoding="utf-8")
    raw = raw.replace("/PLACEHOLDER_INSTALL", str(install))
    raw = raw.replace("/PLACEHOLDER_REPO", str(repo))
    raw = raw.replace("/PLACEHOLDER_HOME", str(home))
    payload = json.loads(raw)
    assert isinstance(payload, dict)
    return payload


def _observe(
    monkeypatch: pytest.MonkeyPatch,
    payload: JsonObject,
    *,
    harness: str = "codex",
    receipts: list[JsonObject] | None = None,
) -> int:
    monkeypatch.setattr("sys.stdin", _FakeStdin(json.dumps(payload)))
    if receipts is not None:
        monkeypatch.setattr(
            "cli.usage.attribution.load_receipts", lambda: receipts
        )
    return main(["usage", "observe", "--harness", harness, "--json"])


def test_usage_pending_empty(capsys: pytest.CaptureFixture[str]) -> None:
    """usage pending with empty spool outputs nothing."""
    assert main(["usage", "pending", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.usage.pending"
    assert payload["data"] == []


def test_usage_pending_with_observations(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """usage pending shows observations from the local spool."""
    spool_observation(_make_test_observation())

    assert main(["usage", "pending", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["data"]) == 1
    assert payload["data"][0]["resource_id"] == "res-001"


def test_usage_pending_exposes_the_group_id_dismiss_needs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The id ``usage dismiss`` takes must be reachable from CLI output.

    Otherwise the companion is told to dismiss a group whose id it has no
    way to learn.
    """
    spool_observation(_make_test_observation(session_hash="group-test"))
    assert main(["usage", "pending", "--json"]) == 0
    group_id = json.loads(capsys.readouterr().out)["data"][0][
        "observation_group_id"
    ]

    assert main(["usage", "dismiss", group_id, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["removed"] == 1
    assert list_pending_observations() == []


def test_usage_pending_since_filter() -> None:
    """usage pending --since filters by recency."""
    spool_observation(_make_test_observation())
    assert main(["usage", "pending", "--since", "24h", "--json"]) == 0
    assert main(["usage", "pending", "--since", "0s", "--json"]) == 0


def test_usage_observe_from_explicit_installation_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """A companion that already knows the installation may report it."""
    set_mode("codex", "prompt")
    install = _install(tmp_path / "repo")
    receipt = _receipt(target_path=install)

    code = _observe(
        monkeypatch,
        {
            "event": "resource_invoked",
            "installation_id": receipt["installation_id"],
            "session_hash": "sess-def",
        },
        receipts=[receipt],
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["disposition"] == "recorded"
    assert payload["data"]["observation"]["resource_id"] == "res-002"
    assert payload["data"]["observation"]["harness"] == "codex"


@pytest.mark.parametrize(
    ("fixture", "harness"),
    [
        ("claude_code_post_tool_use.json", "claude-code"),
        ("codex_post_tool_use.json", "codex"),
    ],
)
def test_native_hook_payload_resolves_to_the_installation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    isolated_logion_home: Path,
    fixture: str,
    harness: str,
) -> None:
    """The recorded payload of each harness attributes without a hint.

    This is the difference between observation and an agent asserting it
    used something: nothing in the payload names a resource.
    """
    set_mode(harness, "prompt")
    repo = tmp_path / "repo"
    install = _install(repo)
    receipt = _receipt(target_path=install, scope_root=repo, harness=harness)
    payload = _load_payload(
        fixture, install=install, repo=repo, home=isolated_logion_home
    )

    assert (
        _observe(monkeypatch, payload, harness=harness, receipts=[receipt])
        == 0
    )

    data = json.loads(capsys.readouterr().out)["data"]
    assert data["disposition"] == "recorded"
    assert data["observation"]["installation_id"] == receipt["installation_id"]


def test_hook_payload_secrets_never_reach_the_spool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolated_logion_home: Path,
) -> None:
    """Prompt, path, command, and session id are dropped after attribution."""
    set_mode("claude-code", "prompt")
    repo = tmp_path / "repo"
    install = _install(repo)
    receipt = _receipt(target_path=install, scope_root=repo)
    payload = _load_payload(
        "claude_code_post_tool_use.json",
        install=install,
        repo=repo,
        home=isolated_logion_home,
    )
    payload["tool_input"]["file_text"] = "AWS_SECRET_ACCESS_KEY=canary42"
    payload["prompt"] = "refactor the billing module in acme-private"

    assert (
        _observe(
            monkeypatch, payload, harness="claude-code", receipts=[receipt]
        )
        == 0
    )

    spool = (isolated_logion_home / "usage" / "observations.jsonl").read_text()
    for canary in (
        "canary42",
        "billing module",
        str(install),
        str(repo),
        "abc123",  # the raw session_id from the fixture
        "SKILL.md",
    ):
        assert canary not in spool, f"{canary!r} leaked into the spool"


def test_observation_in_one_repository_does_not_attach_to_another(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    isolated_logion_home: Path,
) -> None:
    """The same resource in two repositories keeps two identities."""
    set_mode("codex", "prompt")
    xpto = tmp_path / "xpto"
    acme = tmp_path / "acme"
    xpto_install = _install(xpto)
    acme_install = _install(acme)
    xpto_receipt = _receipt(target_path=xpto_install, scope_root=xpto)
    acme_receipt = _receipt(target_path=acme_install, scope_root=acme)
    assert xpto_receipt["installation_id"] != acme_receipt["installation_id"]
    assert xpto_receipt["scope_id"] != acme_receipt["scope_id"]

    payload = _load_payload(
        "codex_post_tool_use.json",
        install=xpto_install,
        repo=xpto,
        home=isolated_logion_home,
    )
    assert (
        _observe(monkeypatch, payload, receipts=[xpto_receipt, acme_receipt])
        == 0
    )

    data = json.loads(capsys.readouterr().out)["data"]
    assert (
        data["observation"]["installation_id"]
        == (xpto_receipt["installation_id"])
    )
    assert data["observation"]["scope_id"] == xpto_receipt["scope_id"]
    assert len(data["observations"]) == 1


def test_unattributed_payload_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    isolated_logion_home: Path,
) -> None:
    """A tool call outside any installation is not a use event."""
    set_mode("codex", "prompt")
    repo = tmp_path / "repo"
    receipt = _receipt(target_path=_install(repo), scope_root=repo)
    payload = {
        "session_id": "s1",
        "tool_name": "Read",
        "tool_input": {"file_path": str(repo / "src" / "main.py")},
    }

    assert _observe(monkeypatch, payload, receipts=[receipt]) == 0

    data = json.loads(capsys.readouterr().out)["data"]
    assert data == {
        "disposition": "ignored",
        "reason": "no_attributed_installation",
    }
    assert not (isolated_logion_home / "usage").exists()


def test_ambiguous_attribution_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Two receipts claiming one path with equal depth resolve to neither."""
    set_mode("codex", "prompt")
    repo = tmp_path / "repo"
    install = _install(repo)
    first = _receipt(target_path=install, scope_root=repo)
    second = {
        **_receipt(target_path=install, scope_root=repo),
        "installation_id": "f" * 64,
        "resource_id": "res-999",
    }
    payload = {
        "session_id": "s1",
        "tool_name": "Read",
        "tool_input": {"file_path": str(install / "SKILL.md")},
    }

    assert _observe(monkeypatch, payload, receipts=[first, second]) == 0

    data = json.loads(capsys.readouterr().out)["data"]
    assert data["reason"] == "no_attributed_installation"


def test_usage_observe_off_writes_nothing_and_reads_nothing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated_logion_home: Path,
) -> None:
    """``off`` short-circuits before stdin, inventory, and the spool."""
    set_mode("codex", "off")
    before = sorted(p.name for p in isolated_logion_home.iterdir())

    def _fail() -> list[JsonObject]:
        raise AssertionError("inventory must not be read when off")

    monkeypatch.setattr("cli.usage.attribution.load_receipts", _fail)
    monkeypatch.setattr("sys.stdin", _FakeStdin('{"tool_name": "Read"}'))

    assert main(["usage", "observe", "--harness", "codex", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["disposition"] == "ignored"
    assert payload["data"]["reason"] == "observation_not_consented"
    assert sorted(p.name for p in isolated_logion_home.iterdir()) == before
    assert not (isolated_logion_home / "usage").exists()


def test_unconfigured_harness_defaults_to_off(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Observation is opt-in: no stored mode means no spool."""
    monkeypatch.setattr("sys.stdin", _FakeStdin('{"tool_name": "Read"}'))
    assert main(["usage", "observe", "--harness", "codex", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["reason"] == "observation_not_consented"


def test_do_not_track_overrides_stored_consent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An external opt-out beats a stored mode."""
    set_mode("codex", "auto")
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    monkeypatch.setattr("sys.stdin", _FakeStdin('{"tool_name": "Read"}'))

    assert main(["usage", "observe", "--harness", "codex", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["mode"] == "off"


def test_usage_observe_always_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """usage observe exits 0 even on invalid input."""
    set_mode("codex", "prompt")
    monkeypatch.setattr("sys.stdin", _FakeStdin("not json"))
    assert main(["usage", "observe", "--harness", "codex", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["disposition"] == "failed"


def test_usage_observe_dedup() -> None:
    """Duplicate observations within the window are not double-counted."""
    obs = _make_test_observation(session_hash="dedup-test")
    spool_observation(obs)
    spool_observation(obs)

    assert len(list_pending_observations()) == 1


def test_concurrent_appends_keep_every_line_parseable(
    isolated_logion_home: Path,
) -> None:
    """Parallel hook invocations must not tear a line."""
    from concurrent.futures import ThreadPoolExecutor

    observations = [
        _make_test_observation(session_hash=f"sess-{index:02d}")
        for index in range(24)
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(spool_observation, observations))

    spool = isolated_logion_home / "usage" / "observations.jsonl"
    lines = [line for line in spool.read_text().splitlines() if line.strip()]
    assert len(lines) == len(observations)
    for line in lines:
        assert isinstance(json.loads(line), dict)


def test_torn_and_unknown_lines_are_skipped(
    isolated_logion_home: Path,
) -> None:
    """A truncated or future-schema line must not break the reader."""
    spool_observation(_make_test_observation())
    spool = isolated_logion_home / "usage" / "observations.jsonl"
    with spool.open("a", encoding="utf-8") as handle:
        handle.write('{"schema_version": 1, "observation_id": "trunc"\n')
        handle.write('{"schema_version": 99, "observation_id": "future"}\n')

    assert len(list_pending_observations()) == 2  # torn line dropped
    assert main(["usage", "pending", "--json"]) == 0


def test_usage_dismiss_no_match(capsys: pytest.CaptureFixture[str]) -> None:
    """usage dismiss with unknown group id removes nothing."""
    assert main(["usage", "dismiss", "nonexistent123", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["removed"] == 0


def test_group_id_is_stable_and_not_stored(
    isolated_logion_home: Path,
) -> None:
    """The group id is derived, so the record keeps its pinned fields."""
    obs = _make_test_observation(session_hash="stable")
    spool_observation(obs)
    stored = json.loads(
        (isolated_logion_home / "usage" / "observations.jsonl")
        .read_text()
        .splitlines()[0]
    )
    assert "observation_group_id" not in stored
    assert observation_group_id(obs) == observation_group_id(obs)


def test_spool_permissions(isolated_logion_home: Path) -> None:
    """Spool directory and file have restrictive permissions."""
    spool_observation(_make_test_observation())

    spool_dir = isolated_logion_home / "usage"
    spool_file = spool_dir / "observations.jsonl"

    assert spool_dir.stat().st_mode & 0o777 == 0o700
    assert spool_file.stat().st_mode & 0o777 == 0o600


class _FakeStdin:
    """Minimal stdin replacement for testing."""

    def __init__(self, data: str) -> None:
        self._data = data

    def read(self) -> str:
        return self._data


def test_deduplicated_observe_reports_the_record_the_spool_holds(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """A deduplicated call must not invent an id `pending` will never show.

    The proving-ground gate caught this: the agent observed twice, the
    second call was deduplicated, and `observe` still answered
    `disposition: recorded` with a fresh observation_id that was nowhere
    in the spool.
    """
    set_mode("codex", "prompt")
    install = _install(tmp_path / "repo")
    receipt = _receipt(target_path=install)
    payload = {
        "event": "resource_invoked",
        "installation_id": receipt["installation_id"],
        "session_hash": "sess-dup",
    }

    assert _observe(monkeypatch, payload, receipts=[receipt]) == 0
    first = json.loads(capsys.readouterr().out)["data"]
    assert first["observation"]["deduplicated"] is False

    assert _observe(monkeypatch, payload, receipts=[receipt]) == 0
    second = json.loads(capsys.readouterr().out)["data"]

    assert second["disposition"] == "recorded"
    assert second["observation"]["deduplicated"] is True
    assert (
        second["observation"]["observation_id"]
        == first["observation"]["observation_id"]
    )

    spooled = list_pending_observations()
    assert len(spooled) == 1
    assert (
        spooled[0]["observation_id"]
        == (second["observation"]["observation_id"])
    )

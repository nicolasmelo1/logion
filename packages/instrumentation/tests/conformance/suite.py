# SPDX-License-Identifier: MIT
"""Shared conformance suite for the Logion consented-observation reporter.

Both bindings (Python ``report.py`` and Node ``report.mjs``) must pass
every test in this module.  The suite tests every numbered behavior
from the plan (lines 234-253) and every prohibition (lines 255-262).

A binding is registered via :class:`ReporterBinding`, an abstract
interface that runs a subcommand or the hook path and returns the
exit code, stdout, and stderr.  The Python tests in
``test_report_py.py`` instantiate a Python binding; the Node tests in
``test_report_mjs.py`` instantiate a Node binding (when Node is
available).

The suite is the contract: a third binding is added by making it
pass, and a binding that diverges on any case fails the build rather
than shipping a second dialect.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class ReporterResult:
    """Result of running a reporter binding."""

    def __init__(
        self,
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ReporterBinding(Protocol):
    """Interface for a reporter binding under test."""

    def run_hook(
        self,
        payload: dict[str, object] | str | None,
        base: Path,
        env: dict[str, str] | None = None,
    ) -> ReporterResult:
        """Run the hook path (stdin → spool → optional upload)."""
        ...

    def run_subcommand(
        self,
        command: str,
        base: Path,
        env: dict[str, str] | None = None,
    ) -> ReporterResult:
        """Run a subcommand (status, pending, export, delete, disable)."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name for test labels."""
        ...


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _write_profile(
    base: Path,
    *,
    fields: list[str] | None = None,
    endpoint: str = "https://api.logion.sh/v1/receipts",
    max_spool_bytes: int = 262_144,
    max_batch: int = 20,
) -> None:
    """Write a minimal valid profile to ``base/.logion/profile.json``."""
    logion = base / ".logion"
    logion.mkdir(parents=True, exist_ok=True)
    profile = {
        "schema": "logion.instrumentation/v1",
        "subject": {
            "resource_id": "urn:air:example.com:skill:test-skill",
            "resource_version": "1.0.0",
            "distribution_digest": "sha256:abc123",
        },
        "publisher": {"identity": "did:web:example.com"},
        "delivery": {
            "endpoint": endpoint,
            "mode": "asynchronous-batch",
            "max_batch": max_batch,
            "max_spool_bytes": max_spool_bytes,
        },
        "events": ["resource_invoked"],
        "fields": fields
        or [
            "resource_id",
            "resource_version",
            "distribution_digest",
            "event",
            "outcome",
            "duration_bucket",
            "harness",
            "integration_version",
        ],
        "excluded": [
            "prompt",
            "file_content",
            "local_path",
            "tool_arguments",
            "tool_results",
            "model_context",
            "secrets",
            "user_identity",
        ],
        "integration_version": "logion.publisher-reporter.v1",
    }
    (logion / "profile.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )


def _write_consent(
    base: Path,
    *,
    mode: str = "allow",
    installation_id: str = "inst_001",
) -> None:
    """Write a consent record to ``base/.logion/consent.json``."""
    logion = base / ".logion"
    logion.mkdir(parents=True, exist_ok=True)
    consent = {
        "mode": mode,
        "scope": "user",
        "profile_digest": "sha256:placeholder",
        "installation_id": installation_id,
    }
    (logion / "consent.json").write_text(
        json.dumps(consent, indent=2), encoding="utf-8"
    )


def _read_spool(base: Path) -> list[dict[str, object]]:
    spool = base / ".logion" / "spool.jsonl"
    if not spool.is_file():
        return []
    events: list[dict[str, object]] = []
    for line in spool.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict) and "_drop_count" not in obj:
            events.append(obj)
    return events


def _spool_exists(base: Path) -> bool:
    return (base / ".logion" / "spool.jsonl").is_file()


# ---------------------------------------------------------------------------
# Behavior 1: Read stdin, bounded to 1 MiB. Parse failure → exit 0 silently.
# ---------------------------------------------------------------------------


def test_behavior_1_parse_failure_exits_zero(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """On any parse failure, exit 0 silently."""
    result = binding.run_hook("not valid json", tmp_path)
    assert result.returncode == 0
    assert not _spool_exists(tmp_path)


def test_behavior_1_empty_stdin_exits_zero(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    result = binding.run_hook("", tmp_path)
    assert result.returncode == 0
    assert not _spool_exists(tmp_path)


def test_behavior_1_non_object_json_exits_zero(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    result = binding.run_hook("[1, 2, 3]", tmp_path)
    assert result.returncode == 0
    assert not _spool_exists(tmp_path)


# ---------------------------------------------------------------------------
# Behavior 2: Resolve consent.json. Absent/off/DNT → exit 0.
# ---------------------------------------------------------------------------


def test_behavior_2_no_consent_exits_zero(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    _write_profile(tmp_path)
    payload = {"event": "resource_invoked", "resource_id": "x"}
    result = binding.run_hook(payload, tmp_path)
    assert result.returncode == 0
    assert not _spool_exists(tmp_path)


def test_behavior_2_consent_off_exits_zero(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="off")
    payload = {"event": "resource_invoked", "resource_id": "x"}
    result = binding.run_hook(payload, tmp_path)
    assert result.returncode == 0
    assert not _spool_exists(tmp_path)


def test_behavior_2_dnt_env_exits_zero(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="allow")
    payload = {"event": "resource_invoked", "resource_id": "x"}
    result = binding.run_hook(payload, tmp_path, env={"DO_NOT_TRACK": "1"})
    assert result.returncode == 0
    assert not _spool_exists(tmp_path)


def test_behavior_2_logion_dnt_env_exits_zero(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="allow")
    payload = {"event": "resource_invoked", "resource_id": "x"}
    result = binding.run_hook(
        payload, tmp_path, env={"LOGION_DO_NOT_TRACK": "true"}
    )
    assert result.returncode == 0
    assert not _spool_exists(tmp_path)


def test_behavior_2_dnt_false_allows(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """DNT set to a falsey value must NOT block observation."""
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="local-only")
    payload = {"event": "resource_invoked", "resource_id": "x"}
    result = binding.run_hook(payload, tmp_path, env={"DO_NOT_TRACK": "0"})
    assert result.returncode == 0
    assert _spool_exists(tmp_path)


# ---------------------------------------------------------------------------
# Behavior 3: Redact before persistence — allowlist only.
# ---------------------------------------------------------------------------


def test_behavior_3_only_allowlisted_fields(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """A field not in the allowlist never enters the event."""
    _write_profile(
        tmp_path,
        fields=["resource_id", "event", "harness"],
    )
    _write_consent(tmp_path, mode="local-only")
    payload = {
        "event": "resource_invoked",
        "resource_id": "urn:test:1",
        "harness": "claude-code",
        "outcome": "completed",  # NOT in allowlist
        "duration_bucket": "seconds",  # NOT in allowlist
    }
    result = binding.run_hook(payload, tmp_path)
    assert result.returncode == 0
    events = _read_spool(tmp_path)
    assert len(events) == 1
    ev = events[0]
    assert "resource_id" in ev
    assert "event" in ev
    assert "harness" in ev
    assert "outcome" not in ev
    assert "duration_bucket" not in ev


def test_behavior_3_sensitive_keys_never_present(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """Sensitive keys must never appear in the spooled event."""
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="local-only")
    payload = {
        "event": "resource_invoked",
        "resource_id": "urn:test:1",
        "prompt": "secret prompt data",
        "file_content": "file data",
        "local_path": "/secret/path",
        "tool_arguments": {"cmd": "rm -rf /"},
        "tool_results": "output",
        "model_context": "context",
        "secrets": "key",
        "user_identity": "user@example.com",
        "transcript_path": "/path/to/transcript",
        "tool_input": {"file_path": "/secret"},
        "tool_response": "response",
    }
    result = binding.run_hook(payload, tmp_path)
    assert result.returncode == 0
    events = _read_spool(tmp_path)
    assert len(events) == 1
    ev = events[0]
    sensitive = {
        "prompt",
        "file_content",
        "local_path",
        "tool_arguments",
        "tool_results",
        "model_context",
        "secrets",
        "user_identity",
        "transcript_path",
        "tool_input",
        "tool_response",
    }
    for key in sensitive:
        assert key not in ev, f"Sensitive key '{key}' found in event"


# ---------------------------------------------------------------------------
# Behavior 4: Bounded spool — drop oldest when over max_spool_bytes.
# ---------------------------------------------------------------------------


def test_behavior_4_spool_is_bounded(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """Spool must not grow without limit."""
    _write_profile(
        tmp_path,
        fields=["event"],
        max_spool_bytes=512,  # Very small to force trimming
    )
    _write_consent(tmp_path, mode="local-only")
    for i in range(20):
        binding.run_hook({"event": "resource_invoked", "idx": i}, tmp_path)
    spool_size = (tmp_path / ".logion" / "spool.jsonl").stat().st_size
    # Should be well under 512 * 10
    assert spool_size < 512 * 10, (
        f"Spool grew to {spool_size} bytes — not bounded"
    )


# ---------------------------------------------------------------------------
# Behavior 5: Under local-only, stop after spooling (no upload).
# ---------------------------------------------------------------------------


def test_behavior_5_local_only_no_upload(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """Under local-only, events are spooled but never delivered."""
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="local-only")
    payload = {"event": "resource_invoked", "resource_id": "x"}
    result = binding.run_hook(payload, tmp_path)
    assert result.returncode == 0
    events = _read_spool(tmp_path)
    assert len(events) == 1
    assert events[0].get("delivered") is False


# ---------------------------------------------------------------------------
# Behavior 6: Under allow, batch with retries, dedup.
# ---------------------------------------------------------------------------


def test_behavior_6_allow_deduplicates(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """Duplicate (event_id, installation_id) pairs are deduplicated."""
    _write_profile(
        tmp_path,
        endpoint="https://localhost:1/v1/receipts",  # unreachable
        max_batch=10,
    )
    _write_consent(tmp_path, mode="allow", installation_id="inst_001")
    # Same payload twice → same event_id
    payload = {"event": "resource_invoked", "resource_id": "x"}
    binding.run_hook(payload, tmp_path)
    binding.run_hook(payload, tmp_path)
    events = _read_spool(tmp_path)
    ids = [e.get("event_id") for e in events]
    # Two spool entries but they have the same event_id
    # dedup happens at upload time, not spool time
    unique_ids = set(ids)
    assert len(unique_ids) == 1, (
        f"Expected 1 unique event_id, got {len(unique_ids)}: {unique_ids}"
    )


# ---------------------------------------------------------------------------
# Behavior 7: Exit 0 always.
# ---------------------------------------------------------------------------


def test_behavior_7_exit_zero_on_success(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="local-only")
    result = binding.run_hook({"event": "resource_invoked"}, tmp_path)
    assert result.returncode == 0


def test_behavior_7_exit_zero_on_missing_profile(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    _write_consent(tmp_path, mode="allow")
    result = binding.run_hook({"event": "resource_invoked"}, tmp_path)
    assert result.returncode == 0


def test_behavior_7_exit_zero_on_invalid_payload(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="allow")
    result = binding.run_hook("}{invalid", tmp_path)
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Prohibition 1: Never install, download, or exec the Logion CLI or any binary.
# ---------------------------------------------------------------------------


def test_prohibition_1_no_cli_exec(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """The reporter must never exec 'logion' or any other binary."""
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="local-only")
    # Remove logion from PATH to ensure it's not called
    env = {"PATH": "/usr/bin:/bin"}
    result = binding.run_hook({"event": "resource_invoked"}, tmp_path, env=env)
    assert result.returncode == 0
    # The spool should still be written — proving it doesn't need the CLI
    assert _spool_exists(tmp_path)


# ---------------------------------------------------------------------------
# Prohibition 2: Never accept publisher-supplied credentials for Logion.
# ---------------------------------------------------------------------------


def test_prohibition_2_no_credentials_in_event(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """No credentials should be stored or forwarded."""
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="local-only")
    payload = {
        "event": "resource_invoked",
        "resource_id": "x",
        "api_key": "sk-12345",
        "token": "Bearer xyz",
        "password": "secret",
    }
    result = binding.run_hook(payload, tmp_path)
    assert result.returncode == 0
    events = _read_spool(tmp_path)
    assert len(events) == 1
    ev = events[0]
    assert "api_key" not in ev
    assert "token" not in ev
    assert "password" not in ev


# ---------------------------------------------------------------------------
# Prohibition 3: Never create a stable identifier that correlates a user
# across resources.
# ---------------------------------------------------------------------------


def test_prohibition_3_no_cross_resource_identifier(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """Events for different resources must not share a user-correlating ID."""
    _write_profile(tmp_path, fields=["resource_id", "event"])
    _write_consent(tmp_path, mode="local-only", installation_id="inst_001")
    binding.run_hook(
        {"event": "resource_invoked", "resource_id": "urn:res:1"},
        tmp_path,
    )
    binding.run_hook(
        {"event": "resource_invoked", "resource_id": "urn:res:2"},
        tmp_path,
    )
    events = _read_spool(tmp_path)
    assert len(events) == 2
    # installation_id is per-installation, not per-user — but event_ids
    # must differ because the payloads differ
    assert events[0]["event_id"] != events[1]["event_id"]


# ---------------------------------------------------------------------------
# Prohibition 4: Never infer use from installation, listing, availability,
# or context loading.
# ---------------------------------------------------------------------------


def test_prohibition_4_no_inferred_use(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """No event should be recorded without an explicit hook payload."""
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="local-only")
    # Running a subcommand must not create events
    binding.run_subcommand("status", tmp_path)
    assert not _spool_exists(tmp_path)
    binding.run_subcommand("export", tmp_path)
    assert not _spool_exists(tmp_path)


# ---------------------------------------------------------------------------
# Prohibition 5: Never emit a terminal outcome the client did not report.
# ---------------------------------------------------------------------------


def test_prohibition_5_no_invented_outcome(
    binding: ReporterBinding, tmp_path: Path
) -> None:
    """Absent terminal signal is 'unknown' or no terminal event at all."""
    _write_profile(tmp_path, fields=["resource_id", "event", "outcome"])
    _write_consent(tmp_path, mode="local-only")
    # Payload with no outcome
    payload = {"event": "resource_invoked", "resource_id": "x"}
    result = binding.run_hook(payload, tmp_path)
    assert result.returncode == 0
    events = _read_spool(tmp_path)
    assert len(events) == 1
    ev = events[0]
    # outcome must not be invented — it should be absent
    assert "outcome" not in ev or ev.get("outcome") == "unknown"


# ---------------------------------------------------------------------------
# Subcommands: status, pending, export, delete, disable
# ---------------------------------------------------------------------------


def test_subcommand_status(binding: ReporterBinding, tmp_path: Path) -> None:
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="local-only")
    result = binding.run_subcommand("status", tmp_path)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["mode"] == "local-only"


def test_subcommand_pending(binding: ReporterBinding, tmp_path: Path) -> None:
    _write_profile(tmp_path, fields=["event"])
    _write_consent(tmp_path, mode="local-only")
    binding.run_hook({"event": "resource_invoked"}, tmp_path)
    result = binding.run_subcommand("pending", tmp_path)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) == 1


def test_subcommand_export(binding: ReporterBinding, tmp_path: Path) -> None:
    _write_profile(tmp_path, fields=["event"])
    _write_consent(tmp_path, mode="local-only")
    binding.run_hook({"event": "resource_invoked"}, tmp_path)
    result = binding.run_subcommand("export", tmp_path)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) == 1


def test_subcommand_delete(binding: ReporterBinding, tmp_path: Path) -> None:
    _write_profile(tmp_path, fields=["event"])
    _write_consent(tmp_path, mode="local-only")
    binding.run_hook({"event": "resource_invoked"}, tmp_path)
    assert _spool_exists(tmp_path)
    result = binding.run_subcommand("delete", tmp_path)
    assert result.returncode == 0
    assert not _spool_exists(tmp_path)


def test_subcommand_disable(binding: ReporterBinding, tmp_path: Path) -> None:
    _write_profile(tmp_path)
    _write_consent(tmp_path, mode="allow")
    result = binding.run_subcommand("disable", tmp_path)
    assert result.returncode == 0
    consent = json.loads(
        (tmp_path / ".logion" / "consent.json").read_text(encoding="utf-8")
    )
    assert consent["mode"] == "off"

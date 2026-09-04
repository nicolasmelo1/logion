from __future__ import annotations

import json
from pathlib import Path

from agent_proving_ground.artifacts import resolve_artifact_path
from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)


def _resolve_pending_artifact(artifacts_dir: Path, path: str) -> Path:
    raw_target = Path(path)
    if not raw_target.is_absolute():
        return resolve_artifact_path(artifacts_dir, path)
    target = raw_target.resolve()
    target.relative_to(artifacts_dir.resolve())
    return target


class FileExistsAssertion(Assertion):
    type = "files.exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        path = params.get("path")
        if not path:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing path parameter",
                evidence=params,
            )
        try:
            target = resolve_artifact_path(ctx.artifacts_dir, path)
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"path": path},
            )
        if target.exists():
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message=f"file exists: {path}",
                evidence={"path": str(target)},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message=f"file missing: {path}",
            evidence={"path": str(target)},
        )


class UsagePendingEmptyAssertion(Assertion):
    type = "files.usage_pending_empty"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        path = params.get("path")
        if not path:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing path parameter",
                evidence=params,
            )
        try:
            target = _resolve_pending_artifact(ctx.artifacts_dir, path)
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"invalid pending usage artifact: {exc}",
                evidence={"path": str(path)},
            )
        items = payload.get("data") if isinstance(payload, dict) else None
        passed = items == []
        return AssertionOutcome(
            type=self.type,
            status="passed" if passed else "failed",
            message=(
                "isolated usage spool is empty"
                if passed
                else "isolated usage spool contains observations"
            ),
            evidence={
                "path": str(target),
                "pending_count": (
                    len(items) if isinstance(items, list) else None
                ),
            },
        )


class ObservationFromLiveHookAssertion(Assertion):
    """Prove the recorded observation came from the harness, not a replay.

    Every other observation assertion is satisfied by piping a recorded
    payload into the hook command by hand, which proves the CLI parses a
    payload and nothing about whether a harness ever delivered one. The
    shim on the agent's PATH keeps the stdin of the invocation that
    actually recorded an observation; a payload the harness produced names
    a transcript that exists on this machine, while a checked-in fixture
    carries placeholder paths that resolve nowhere.

    Four checks separate a delivered payload from a typed one, and none of
    them is the scenario prose asking the agent not to type one. The argv is
    deliberately *not* among them: ``integrations enable`` writes the hook as
    ``logion usage observe --harness H --stdin``, so an agent typing that
    string produces a byte-identical command line and argv discriminates
    nothing.

    1. The transcript the payload names must exist **and contain the
       session_id it claims**. A harness transcript names its own session;
       an arbitrary existing file does not, so pointing at one no longer
       passes.
    2. The transcript must sit outside every root the agent can write. A
       transcript the agent could have authored is not evidence about the
       harness.
    3. The payload must carry the harness's own event fields
       (``hook_event_name`` and a tool identifier). A hand-assembled minimal
       observation does not reconstruct them.
    4. A live hook fires on every matching tool call, so a run holds many
       invocations of which one recorded. Exactly one invocation is the
       signature of a single typed command.

    Residual limit, stated rather than papered over: an agent that reads the
    harness's own transcript, lifts its session id, and replays it would
    still pass. Nothing inside the same trust domain as the agent can close
    that, and by then the harness demonstrably ran the session anyway.
    """

    type = "files.observation_from_live_hook"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        raw_dir = params.get("invocations_dir")
        if not raw_dir:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing invocations_dir parameter",
                evidence=params,
            )
        try:
            records_dir = _resolve_pending_artifact(
                ctx.artifacts_dir, str(raw_dir)
            )
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"invocations_dir": str(raw_dir)},
            )
        attempts = sorted(records_dir.glob("*.stdin.json"))
        recorded = records_dir / "recorded.stdin.json"
        if not recorded.is_file():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    "no hook invocation recorded an observation"
                    if attempts
                    else "the harness never ran the installed hook"
                ),
                evidence={
                    "invocations_dir": str(records_dir),
                    "invocations": len(attempts),
                },
            )
        agent_roots = [
            str(root)
            for root in (params.get("agent_writable_roots") or [])
            if str(root).strip()
        ]
        reason = _live_hook_verdict(recorded, agent_roots, len(attempts))
        return AssertionOutcome(
            type=self.type,
            status="failed" if reason else "passed",
            message=(
                f"recorded observation is not from a live hook: {reason}"
                if reason
                else "the harness delivered the payload that was recorded"
            ),
            evidence={
                "payload": str(recorded),
                "invocations": len(attempts),
                "agent_writable_roots": agent_roots,
            },
        )


#: A hook that fires on tool calls invokes the CLI far more often than it
#: records. One invocation total means one command ran, which is what typing
#: it by hand looks like.
_MIN_LIVE_HOOK_INVOCATIONS = 2


def _live_hook_verdict(
    path: Path,
    agent_writable_roots: list[str],
    invocations: int,
) -> str | None:
    """``None`` if *path* holds a live harness payload, else the reason."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return f"unreadable payload: {exc}"
    if not isinstance(payload, dict):
        return "payload is not an object"
    raw = path.read_text(encoding="utf-8")
    if "PLACEHOLDER" in raw:
        return "carries fixture placeholders"
    if invocations < _MIN_LIVE_HOOK_INVOCATIONS:
        return (
            f"only {invocations} hook invocation in the run; a hook firing "
            "on tool calls invokes the CLI more than once"
        )
    if not payload.get("hook_event_name"):
        return "no hook_event_name: the harness did not name the event"
    if not (payload.get("tool_use_id") or payload.get("tool_name")):
        return "no tool identifier: the payload names no tool call"
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return "no session_id"
    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return "no transcript_path"
    return _transcript_verdict(transcript, session_id, agent_writable_roots)


def _transcript_verdict(
    transcript: str,
    session_id: str,
    agent_writable_roots: list[str],
) -> str | None:
    """``None`` if the transcript corroborates the payload, else the reason."""
    path = Path(transcript)
    if not path.exists():
        return f"transcript_path does not exist: {transcript}"
    try:
        resolved = path.resolve()
    except OSError as exc:
        return f"transcript_path does not resolve: {exc}"
    for raw_root in agent_writable_roots:
        try:
            root = Path(raw_root).resolve()
        except OSError:
            continue
        if resolved == root or root in resolved.parents:
            return (
                "transcript_path is inside a root the agent can write "
                f"({root}), so it is not evidence about the harness"
            )
    try:
        # Transcripts are append-only JSONL and can be large; the session id
        # is stamped on every entry, so the head is enough and a run never
        # pays for reading a multi-megabyte log.
        with resolved.open("r", encoding="utf-8", errors="replace") as handle:
            head = handle.read(1_000_000)
    except OSError as exc:
        return f"transcript_path is unreadable: {exc}"
    # Claude Code names the file after the session and stamps the id on every
    # entry; other harnesses do one or the other. Either corroborates.
    if session_id not in head and session_id not in resolved.name:
        return (
            f"transcript {resolved} does not name session {session_id}: the "
            "payload claims a session the transcript did not record"
        )
    return None


class EvalAgentPerformedAssertion(Assertion):
    """Require the operator's recorded turn and its public CLI outputs.

    The eval evidence collector can inspect server state, but it cannot stand
    in for the consumer role performing the two local eval runs.  This check
    ties the driver transcript to the raw files copied from that role and
    rejects a launcher record that merely repeats a completion claim.
    """

    type = "files.eval_agent_performed"
    _RAW_ARTIFACTS = ("run-one.json", "run-two.json", "run-summary.json")
    _REQUIRED_COMMANDS = (
        "logion-node eval validate",
        "logion-node eval run",
        "logion-node eval compare",
    )

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        transcript_raw = params.get("transcript")
        raw_dir_raw = params.get("raw_dir")
        if not transcript_raw or not raw_dir_raw:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="transcript and raw_dir parameters are required",
                evidence=params,
            )
        try:
            transcript = _resolve_pending_artifact(
                ctx.artifacts_dir, str(transcript_raw)
            )
            raw_dir = _resolve_pending_artifact(
                ctx.artifacts_dir, str(raw_dir_raw)
            )
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={
                    "transcript": transcript_raw,
                    "raw_dir": raw_dir_raw,
                },
            )
        try:
            transcript_text = transcript.read_text(encoding="utf-8")
        except OSError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"cannot read process-driver transcript: {exc}",
                evidence={"transcript": str(transcript)},
            )
        if transcript.name != "node_operator_eval_flow.md":
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="transcript is not the node_operator_eval_flow turn",
                evidence={"transcript": str(transcript)},
            )
        if "RESULT: COMPLETED" not in transcript_text.upper():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="process-driver transcript lacks RESULT: completed",
                evidence={"transcript": str(transcript)},
            )
        if "run-eval-flow.sh" not in transcript_text:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="process-driver transcript does not name the launcher",
                evidence={"transcript": str(transcript)},
            )
        missing = [
            name
            for name in self._RAW_ARTIFACTS
            if not (raw_dir / name).is_file()
        ]
        if missing:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing agent-produced raw artifacts: "
                + ", ".join(missing),
                evidence={"raw_dir": str(raw_dir), "missing": missing},
            )
        invalid = [
            name
            for name in self._RAW_ARTIFACTS
            if not _is_json_object(raw_dir / name)
        ]
        if invalid:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="invalid agent-produced raw artifacts: "
                + ", ".join(invalid),
                evidence={"raw_dir": str(raw_dir), "invalid": invalid},
            )
        record = raw_dir / "launcher-record.json"
        verdict = _eval_launcher_verdict(record)
        return AssertionOutcome(
            type=self.type,
            status="passed" if verdict is None else "failed",
            message=(
                "operator completed the prepared public logion-node workflow"
                if verdict is None
                else (
                    "launcher record is not evidence of the eval flow: "
                    f"{verdict}"
                )
            ),
            evidence={
                "transcript": str(transcript),
                "raw_dir": str(raw_dir),
                "launcher_record": str(record),
            },
        )


def _is_json_object(path: Path) -> bool:
    try:
        return isinstance(json.loads(path.read_text(encoding="utf-8")), dict)
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _eval_launcher_verdict(record: Path) -> str | None:
    """Return why the launcher log is insufficient, or ``None`` when live."""
    try:
        payload = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return f"unreadable launcher record: {exc}"
    commands = payload.get("commands") if isinstance(payload, dict) else None
    if not isinstance(commands, list) or not commands:
        return "no commands with exits"
    observed: list[str] = []
    run_count = 0
    for entry in commands:
        if not isinstance(entry, dict):
            return "command entry is not an object"
        command = entry.get("command")
        exit_code = entry.get("exit_code")
        if not isinstance(command, str) or not command.strip():
            return "command entry has no command"
        if not isinstance(exit_code, int):
            return "command entry has no integer exit_code"
        if exit_code != 0:
            return f"command exited {exit_code}: {command}"
        observed.append(command)
        if "logion-node eval run" in command:
            run_count += 1
    missing = [
        command
        for command in EvalAgentPerformedAssertion._REQUIRED_COMMANDS
        if not any(
            command in observed_command for observed_command in observed
        )
    ]
    if missing or run_count < 2:
        detail = ", ".join(missing)
        if run_count < 2:
            detail = (
                f"{detail}; two eval runs required"
                if detail
                else "two eval runs required"
            )
        return f"missing real public CLI commands ({detail})"
    return None


class ClientHasNoARDConnectorInstallAssertion(Assertion):
    """Verify that no ARD connector files or finder preferences were
    installed into the client workspace."""

    type = "files.client_has_no_ard_connector_install"

    _CONNECTOR_MARKERS = (
        ".agentfinder",
        ".ard-connectors",
        "agentfinder.json",
    )

    async def evaluate(
        self,
        ctx: AssertionContext,  # noqa: ARG002
        params: dict,
    ) -> AssertionOutcome:
        workspace_root = params.get("workspace_root")
        if not workspace_root:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing workspace_root parameter",
                evidence=params,
            )
        root = Path(workspace_root).resolve()  # noqa: ASYNC240
        if not root.is_dir():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"workspace_root does not exist: {root}",
                evidence={"workspace_root": str(root)},
            )
        found: list[str] = []
        for marker in self._CONNECTOR_MARKERS:
            candidate = root / marker
            if candidate.exists():
                found.append(str(candidate))
        # Also check home dir for ~/.agentfinder
        home = Path.home()
        home_marker = home / ".agentfinder"
        if home_marker.exists():
            found.append(str(home_marker))
        passed = not found
        return AssertionOutcome(
            type=self.type,
            status="passed" if passed else "failed",
            message=(
                "no ARD connector files or finder preferences in workspace"
                if passed
                else f"found connector artifacts: {', '.join(found)}"
            ),
            evidence={
                "workspace_root": str(root),
                "found_paths": found,
            },
        )


def _load_role_manifest(ctx: AssertionContext, params: dict) -> dict:
    """Read a role evidence manifest written by a local hook.

    Every sandbox assertion reads a manifest the run itself produced —
    the operator hook captures ``docker inspect`` facts, ``id -u``,
    canary probes, and scope checks per role. A missing or malformed
    manifest is a failure, not ``unsupported``: the phase gate is
    required, and "we did not look" is exactly the answer it exists to
    reject.
    """
    path = params.get("manifest")
    if not path:
        raise ValueError("manifest parameter is required")
    target = _resolve_pending_artifact(ctx.artifacts_dir, path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("role manifest is not a JSON object")
    return payload


def _identity_evidence(
    manifest: dict, roles: dict, observed: dict[str, object]
) -> dict:
    """Retain the full identity manifest facts alongside the assertion."""
    return {
        "roles": observed,
        "runtime": manifest.get("runtime"),
        "compose_sha256": manifest.get("compose_sha256"),
        "dockerfile_sha256": manifest.get("dockerfile_sha256"),
        "role_agent_ids": manifest.get("role_agent_ids"),
        "credential_fingerprints": manifest.get("credential_fingerprints"),
        "prompts": manifest.get("prompts"),
        "role_runtime": {
            role: {
                "container_id": entry.get("container_id"),
                "image_id": entry.get("image_id"),
                "versions": entry.get("versions"),
                "mounts": entry.get("mounts"),
            }
            for role, entry in roles.items()
            if isinstance(entry, dict)
        },
    }


def _outcome(
    assertion_type: str, ok: bool, ok_msg: str, fail_msg: str, evidence: dict
) -> AssertionOutcome:
    return AssertionOutcome(
        type=assertion_type,
        status="passed" if ok else "failed",
        message=ok_msg if ok else fail_msg,
        evidence=evidence,
    )


def _nonroot_offender(entry: dict) -> str | None:
    uid = entry.get("uid")
    expected = entry.get("expected_uid")
    if not isinstance(uid, int) or uid == 0:
        return f"uid={uid}"
    if expected is not None and uid != expected:
        return f"uid={uid}!={expected}"
    if entry.get("home_writable") is not True:
        return "home-not-writable"
    return None


def _limits_offender(entry: dict) -> str | None:
    limits = entry.get("limits")
    if not isinstance(limits, dict):
        return "no-limits"
    missing = [
        key
        for key in ("cpus", "memory_bytes", "pids", "wall_time_seconds")
        if limits.get(key) is None
    ]
    if missing:
        return f"missing-{','.join(missing)}"
    if limits.get("wall_time_enforced") is not True:
        return f"wall_time_enforced={limits.get('wall_time_enforced')}"
    return None


class SandboxRolesRunNonRootAssertion(Assertion):
    """Every role container runs as its declared non-root UID."""

    type = "sandbox.roles_run_non_root"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        try:
            manifest = _load_role_manifest(ctx, params)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"role manifest unreadable: {exc}",
                evidence=params,
            )
        roles = manifest.get("roles")
        if not isinstance(roles, dict) or not roles:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="role manifest carries no roles object",
                evidence=params,
            )
        offenders: list[str] = []
        observed: dict[str, object] = {}
        for role, entry in sorted(roles.items()):
            if not isinstance(entry, dict):
                offenders.append(role)
                continue
            offender = _nonroot_offender(entry)
            if offender is not None:
                offenders.append(f"{role}:{offender}")
            observed[role] = {
                "uid": entry.get("uid"),
                "user": entry.get("user"),
                "home_writable": entry.get("home_writable"),
            }
        return _outcome(
            self.type,
            not offenders,
            "all role containers run as their declared non-root UIDs",
            f"non-root violation: {', '.join(offenders)}",
            _identity_evidence(manifest, roles, observed),
        )


class SandboxRoleResourceLimitsEnforcedAssertion(Assertion):
    """Each role runs with declared CPU, memory, PID, and wall-time limits."""

    type = "sandbox.role_resource_limits_enforced"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        try:
            manifest = _load_role_manifest(ctx, params)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"role manifest unreadable: {exc}",
                evidence=params,
            )
        roles = manifest.get("roles")
        if not isinstance(roles, dict) or not roles:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="role manifest carries no roles object",
                evidence=params,
            )
        offenders: list[str] = []
        observed: dict[str, object] = {}
        for role, entry in sorted(roles.items()):
            if not isinstance(entry, dict):
                offenders.append(role)
                continue
            offender = _limits_offender(entry)
            if offender is not None:
                offenders.append(f"{role}:{offender}")
            observed[role] = entry.get("limits")
        return AssertionOutcome(
            type=self.type,
            status="passed" if not offenders else "failed",
            message=(
                "every role runs with declared CPU, memory, PID, and "
                "wall-time limits"
                if not offenders
                else f"limits violation: {', '.join(offenders)}"
            ),
            evidence={"roles": observed},
        )


def _required_canaries() -> set[str]:
    return {
        f"{role}_sees_{probe}"
        for role in ("consumer", "auditor")
        for probe in (
            "host_home",
            "host_keychain",
            "docker_socket",
            "peer_home",
            "peer_credential",
            "peer_spool",
            "peer_workspace",
        )
    }


def _canary_findings(
    canaries: dict,
) -> tuple[list[str], dict[str, object]]:
    offenders: list[str] = []
    observed: dict[str, object] = {}
    for probe, entry in sorted(canaries.items()):
        if not isinstance(entry, dict):
            offenders.append(probe)
            continue
        if entry.get("readable"):
            offenders.append(probe)
        observed[probe] = {
            "readable": entry.get("readable"),
            "role": entry.get("role"),
        }
    return offenders, observed


def _harness_role_offender(entry: dict, role: str) -> list[str]:
    proof = entry.get("proof")
    marker = f"LOGION_HARNESS_OK {role}"
    command_output = (
        proof.replace(marker, "").strip() if isinstance(proof, str) else ""
    )
    offenders: list[str] = []
    if entry.get("process_exit_code") != 0:
        offenders.append("process-exit")
    if entry.get("proof_read_exit_code") != 0:
        offenders.append("proof-unreadable")
    if not command_output or "logion" not in command_output.lower():
        offenders.append("logion-proof-missing")
    if not isinstance(proof, str) or marker not in proof:
        offenders.append("completion-marker-missing")
    codex_version = entry.get("codex_version")
    if not isinstance(codex_version, str) or "codex" not in codex_version:
        offenders.append("codex-version-missing")
    return offenders


def _harness_findings(runs: object) -> tuple[dict, list[str]]:
    expected_roles = {"consumer", "auditor"}
    offenders: list[str] = []
    if not isinstance(runs, dict) or set(runs) != expected_roles:
        offenders.append("role-set-incomplete")
        runs = runs if isinstance(runs, dict) else {}
    for role in sorted(expected_roles):
        entry = runs.get(role)
        if not isinstance(entry, dict):
            offenders.append(f"{role}:missing")
            continue
        offenders.extend(
            f"{role}:{item}" for item in _harness_role_offender(entry, role)
        )
    return runs, offenders


class SandboxCrossVolumeCanaryUnreadableAssertion(Assertion):
    """Host, keychain, socket, and cross-role canaries are unreadable."""

    type = "sandbox.cross_volume_canary_unreadable"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        try:
            manifest = _load_role_manifest(ctx, params)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"role manifest unreadable: {exc}",
                evidence=params,
            )
        canaries = manifest.get("canaries")
        if not isinstance(canaries, dict) or not canaries:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="role manifest carries no canaries object",
                evidence=params,
            )
        missing = sorted(_required_canaries() - set(canaries))
        offenders, observed = _canary_findings(canaries)
        ok = not offenders and not missing
        if missing:
            fail = f"missing required canaries: {', '.join(missing)}"
        else:
            fail = "canary readable from inside a role: " + ", ".join(
                offenders
            )
        return _outcome(
            self.type,
            ok,
            "host and cross-role canaries are unreadable from every role",
            fail,
            {"canaries": observed},
        )


class SandboxRealHarnessUsesLogionAssertion(Assertion):
    """A real in-container harness process invokes the installed Logion CLI."""

    type = "sandbox.real_harness_uses_logion"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        try:
            manifest = _load_role_manifest(ctx, params)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"harness manifest unreadable: {exc}",
                evidence=params,
            )
        runs, harness_offenders = _harness_findings(
            manifest.get("harness_runs")
        )
        observed = {
            role: {
                "process_exit_code": entry.get("process_exit_code"),
                "proof_read_exit_code": entry.get("proof_read_exit_code"),
                "proof": entry.get("proof"),
                "prompt": entry.get("prompt"),
                "codex_version": entry.get("codex_version"),
            }
            for role, entry in sorted(runs.items())
            if isinstance(entry, dict)
        }
        # The auditor recomputes this verdict from typed facts, so every field
        # the contract requires goes out at the evidence root in the
        # {"ok": true, "value": ...} envelope a fact must carry to even be
        # read — including when nothing observed it: a fact everywhere absent
        # reads as "not retained", which hides what the capture skipped
        # behind a bookkeeping code. ``ok`` means observed for every role;
        # None is the hook's unobserved marker and fails the fact instead of
        # standing in for an observation. Whether an observed value is
        # *acceptable* (exit 0, non-empty proof) is the contract's job via
        # expected/forbidden values, not the handler's.
        fields = (
            "process_exit_code",
            "proof_read_exit_code",
            "proof",
            "prompt",
            "codex_version",
        )
        evidence: dict[str, object] = {"harness_runs": observed}
        for field in fields:
            value: dict[str, object] = {
                role: entry[field]
                for role, entry in observed.items()
                if field in entry
            }
            taken = bool(value) and all(
                entry.get(field) is not None for entry in observed.values()
            )
            fact: dict[str, object] = {"ok": taken}
            if not taken:
                fact["failure"] = "missing"
            fact["value"] = value
            evidence[field] = fact
        return _outcome(
            self.type,
            not harness_offenders,
            "real Codex processes inside both role containers used Logion",
            "in-container harness proof failed: "
            + ", ".join(harness_offenders),
            evidence,
        )


class InstallScopedToRepositoryAssertion(Assertion):
    """A repository install is visible in its repo and nowhere else."""

    type = "files.install_scoped_to_repository"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        try:
            manifest = _load_role_manifest(ctx, params)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"role manifest unreadable: {exc}",
                evidence=params,
            )
        scope = manifest.get("repository_scope")
        if not isinstance(scope, dict):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="role manifest carries no repository_scope object",
                evidence=params,
            )
        expected_checks = {
            "visible_in_xpto": True,
            "absent_from_abc": True,
            "absent_from_user_scope": True,
            "absent_from_auditor": True,
        }
        offenders: list[str] = []
        observed: dict[str, object] = {}
        for check, expected in expected_checks.items():
            actual = scope.get(check)
            observed[check] = actual
            if actual is not expected:
                offenders.append(f"{check}={actual}")
        return AssertionOutcome(
            type=self.type,
            status="passed" if not offenders else "failed",
            message=(
                "fixture is visible in XPTO only: absent from ABC, user "
                "scope, and the auditor role"
                if not offenders
                else f"repository scope violation: {', '.join(offenders)}"
            ),
            evidence={"repository_scope": observed},
        )


class RoleCleanupCompleteAssertion(Assertion):
    """Selective reset removed one role's state, the other survives."""

    type = "files.role_cleanup_complete"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        try:
            manifest = _load_role_manifest(ctx, params)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"role manifest unreadable: {exc}",
                evidence=params,
            )
        cleanup = manifest.get("selective_reset")
        if not isinstance(cleanup, dict):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="role manifest carries no selective_reset object",
                evidence=params,
            )
        expected_checks = {
            "consumer_state_removed": True,
            "consumer_key_rejected": True,
            "consumer_new_key_accepted": True,
            "auditor_state_preserved": True,
            "auditor_key_accepted": True,
        }
        offenders: list[str] = []
        observed: dict[str, object] = {}
        for check, expected in expected_checks.items():
            actual = cleanup.get(check)
            observed[check] = actual
            if actual is not expected:
                offenders.append(f"{check}={actual}")
        for check in ("reset_exit_code", "up_exit_code"):
            actual = cleanup.get(check)
            observed[check] = actual
            if actual != 0:
                offenders.append(f"{check}={actual}")
        return AssertionOutcome(
            type=self.type,
            status="passed" if not offenders else "failed",
            message=(
                "consumer reset removed only consumer state; auditor "
                "remains usable"
                if not offenders
                else f"selective reset incomplete: {', '.join(offenders)}"
            ),
            evidence={"selective_reset": observed},
        )

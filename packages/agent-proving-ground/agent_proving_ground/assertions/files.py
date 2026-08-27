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
        reason = _live_hook_verdict(recorded)
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
            },
        )


def _live_hook_verdict(path: Path) -> str | None:
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
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return "no session_id"
    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return "no transcript_path"
    if not Path(transcript).exists():
        return f"transcript_path does not exist: {transcript}"
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


def _role_manifest_or_failure(
    ctx: AssertionContext, params: dict, label: str
) -> tuple[dict | None, AssertionOutcome | None]:
    try:
        return _load_role_manifest(ctx, params), None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, AssertionOutcome(
            type=label,
            status="failed",
            message=f"role manifest unreadable: {exc}",
            evidence=params,
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
        return _outcome(
            self.type,
            not harness_offenders,
            "real Codex processes inside both role containers used Logion",
            "in-container harness proof failed: "
            + ", ".join(harness_offenders),
            {"harness_runs": observed},
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

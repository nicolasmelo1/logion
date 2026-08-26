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

"""Assertion proving the driven node operator performed the runner flow."""

from __future__ import annotations

import json
from pathlib import Path

from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)

_REQUIRED_OPERATOR_ARTIFACTS = (
    "launcher-command.json",
    "run-summary.json",
    "raw-outputs",
)


def _transcript_verdict(transcript: Path) -> str | None:
    try:
        transcript_text = transcript.read_text(encoding="utf-8")
    except OSError:
        return f"missing operator transcript: {transcript.name}"
    if transcript.name != "node_operator_runner_flow.md":
        return "transcript is not the node_operator_runner_flow turn"
    if "RESULT: COMPLETED" not in transcript_text.upper():
        return "operator transcript lacks RESULT: completed"
    if "run-prepared-node-workflow.sh" not in transcript_text:
        return "operator transcript does not name the launcher"
    return None


def _launcher_and_summary_verdict(evidence_dir: Path) -> str | None:
    for name in _REQUIRED_OPERATOR_ARTIFACTS:
        if not (evidence_dir / name).exists():
            return f"missing operator artifact: {name}"
    try:
        launcher = json.loads(
            (evidence_dir / "launcher-command.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, json.JSONDecodeError):
        return "launcher command record is unreadable"
    if not isinstance(launcher, dict) or launcher.get("exit_code") != 0:
        return "launcher command did not exit successfully"
    try:
        summary = json.loads(
            (evidence_dir / "run-summary.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return "run summary is unreadable"
    if not isinstance(summary, dict):
        return "run summary is not an object"
    return None


def _raw_outputs_verdict(evidence_dir: Path) -> str | None:
    raw_dir = evidence_dir / "raw-outputs"
    raw_files = sorted(raw_dir.glob("runner-pass-*.json"))
    if not raw_files:
        return "missing raw logion-node runner output"
    for raw_file in raw_files:
        try:
            payload = json.loads(raw_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return f"raw runner output is unreadable: {raw_file.name}"
        command = payload.get("command") if isinstance(payload, dict) else None
        is_public_run = isinstance(command, list) and any(
            "logion-node" in str(part) for part in command
        )
        if not is_public_run or payload.get("exit_code") != 0:
            return (
                "raw runner output is not a successful logion-node run: "
                f"{raw_file.name}"
            )
    return None


def validate_runner_operator_workspace(
    transcript: Path, evidence_dir: Path
) -> str | None:
    """Return an error for missing driver/product evidence, else ``None``."""
    return (
        _transcript_verdict(transcript)
        or _launcher_and_summary_verdict(evidence_dir)
        or _raw_outputs_verdict(evidence_dir)
    )


def _resolve_paths(
    artifacts_dir: Path, transcript_raw: object, evidence_dir_raw: object
) -> tuple[Path, Path]:
    transcript = Path(str(transcript_raw)).expanduser()
    evidence_dir = Path(str(evidence_dir_raw)).expanduser()
    if not transcript.is_absolute():
        transcript = artifacts_dir / transcript
    if not evidence_dir.is_absolute():
        evidence_dir = artifacts_dir / evidence_dir
    return transcript, evidence_dir


class RunnerAgentPerformedAssertion(Assertion):
    """Tie the process-driver turn to retained public runner CLI outputs."""

    type = "files.runner_agent_performed"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        transcript_raw = params.get("transcript")
        evidence_dir_raw = params.get("evidence_dir")
        if not transcript_raw or not evidence_dir_raw:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="transcript and evidence_dir parameters are required",
                evidence=params,
            )
        transcript, evidence_dir = _resolve_paths(
            ctx.artifacts_dir, transcript_raw, evidence_dir_raw
        )
        verdict = validate_runner_operator_workspace(transcript, evidence_dir)
        return AssertionOutcome(
            type=self.type,
            status="passed" if verdict is None else "failed",
            message=(
                "operator completed the prepared public logion-node runner "
                "workflow"
                if verdict is None
                else verdict
            ),
            evidence={
                "transcript": str(transcript),
                "evidence_dir": str(evidence_dir),
            },
        )

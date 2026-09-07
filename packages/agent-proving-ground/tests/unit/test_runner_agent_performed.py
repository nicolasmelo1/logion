from __future__ import annotations

import json
from pathlib import Path

from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.runner_agent_performed import (
    RunnerAgentPerformedAssertion,
    validate_runner_operator_workspace,
)
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


def _context(root: Path) -> AssertionContext:
    return AssertionContext(
        scenario_name="isolated_runner_node",
        phase_id="node_operator_runner_flow",
        world=World(run_id="r1", base_url="http://mock", root_dir=root),
        api=MockApiAdapter(),
        artifacts_dir=root,
        timeline=Timeline(root / "timeline.jsonl"),
    )


def _operator_workspace(tmp_path: Path) -> tuple[Path, Path]:
    transcript = tmp_path / "node_operator_runner_flow.md"
    transcript.write_text(
        "Ran run-prepared-node-workflow.sh.\nRESULT: completed\n",
        encoding="utf-8",
    )
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "run-summary.json").write_text("{}\n", encoding="utf-8")
    (evidence / "launcher-command.json").write_text(
        json.dumps({"exit_code": 0}), encoding="utf-8"
    )
    raw = evidence / "raw-outputs"
    raw.mkdir()
    (raw / "runner-pass-01.json").write_text(
        json.dumps({
            "command": ["/venv/bin/logion-node", "run", "--once"],
            "exit_code": 0,
        }),
        encoding="utf-8",
    )
    return transcript, evidence


def test_runner_operator_validator_requires_driver_transcript_and_outputs(
    tmp_path: Path,
) -> None:
    transcript, evidence = _operator_workspace(tmp_path)
    assert validate_runner_operator_workspace(transcript, evidence) is None


async def test_runner_operator_assertion_passes_for_completed_public_cli_turn(
    tmp_path: Path,
) -> None:
    transcript, evidence = _operator_workspace(tmp_path)
    result = await RunnerAgentPerformedAssertion().evaluate(
        _context(tmp_path),
        {"transcript": str(transcript), "evidence_dir": str(evidence)},
    )
    assert result.status == "passed", result.message


def test_runner_operator_validator_rejects_blocked_or_missing_product_output(
    tmp_path: Path,
) -> None:
    transcript, evidence = _operator_workspace(tmp_path)
    transcript.write_text("RESULT: blocked\n", encoding="utf-8")
    assert validate_runner_operator_workspace(transcript, evidence) == (
        "operator transcript lacks RESULT: completed"
    )

    transcript.write_text(
        "Ran run-prepared-node-workflow.sh.\nRESULT: completed\n",
        encoding="utf-8",
    )
    (evidence / "raw-outputs" / "runner-pass-01.json").unlink()
    assert validate_runner_operator_workspace(transcript, evidence) == (
        "missing raw logion-node runner output"
    )

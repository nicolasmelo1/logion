"""The eval gate accepts a real operator turn, not a typed completion."""

from __future__ import annotations

import json
from pathlib import Path

from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.files import EvalAgentPerformedAssertion
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


def _context(root: Path) -> AssertionContext:
    return AssertionContext(
        scenario_name="eval_contract_reference_runner",
        phase_id="node_operator_eval_flow",
        world=World(run_id="r1", base_url="http://mock", root_dir=root),
        api=MockApiAdapter(),
        artifacts_dir=root,
        timeline=Timeline(root / "timeline.jsonl"),
    )


def _performed(root: Path) -> dict[str, str]:
    transcript = (
        root / "agents" / "node_operator" / "node_operator_eval_flow.md"
    )
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        "# Agent turn\nOutput:\nRan /workspace/task/eval-flow/"
        "run-eval-flow.sh.\nRESULT: completed\n",
        encoding="utf-8",
    )
    raw = root / "eval-raw"
    raw.mkdir()
    for name in ("run-one.json", "run-two.json", "run-summary.json"):
        (raw / name).write_text("{}\n", encoding="utf-8")
    (raw / "launcher-record.json").write_text(
        json.dumps({
            "commands": [
                {
                    "command": "logion-node eval validate contract.json",
                    "exit_code": 0,
                },
                {
                    "command": (
                        "logion-node eval run --subject subject.json "
                        "contract.json"
                    ),
                    "exit_code": 0,
                },
                {
                    "command": (
                        "logion-node eval run --subject subject.json "
                        "contract.json"
                    ),
                    "exit_code": 0,
                },
                {
                    "command": "logion-node eval compare one.json two.json",
                    "exit_code": 0,
                },
            ]
        }),
        encoding="utf-8",
    )
    return {"transcript": str(transcript), "raw_dir": str(raw)}


def _replace_transcript(params: dict[str, str], text: str) -> None:
    Path(params["transcript"]).write_text(text, encoding="utf-8")


async def test_passes_for_completed_turn_with_real_launcher_record(
    tmp_path: Path,
) -> None:
    result = await EvalAgentPerformedAssertion().evaluate(
        _context(tmp_path), _performed(tmp_path)
    )

    assert result.status == "passed", result.message


async def test_fails_without_a_completed_driver_transcript(
    tmp_path: Path,
) -> None:
    params = _performed(tmp_path)
    _replace_transcript(params, "RESULT: failed\n")

    result = await EvalAgentPerformedAssertion().evaluate(
        _context(tmp_path), params
    )

    assert result.status == "failed"
    assert "RESULT: completed" in result.message


async def test_fails_when_completed_turn_does_not_name_the_launcher(
    tmp_path: Path,
) -> None:
    params = _performed(tmp_path)
    _replace_transcript(params, "RESULT: completed\n")

    result = await EvalAgentPerformedAssertion().evaluate(
        _context(tmp_path), params
    )

    assert result.status == "failed"
    assert "launcher" in result.message


async def test_fails_when_raw_artifact_is_missing(tmp_path: Path) -> None:
    params = _performed(tmp_path)
    (Path(params["raw_dir"]) / "run-two.json").unlink()

    result = await EvalAgentPerformedAssertion().evaluate(
        _context(tmp_path), params
    )

    assert result.status == "failed"
    assert "run-two.json" in result.message


async def test_fails_on_tautological_or_unsuccessful_launcher_record(
    tmp_path: Path,
) -> None:
    params = _performed(tmp_path)
    record = Path(params["raw_dir"]) / "launcher-record.json"
    record.write_text(
        json.dumps({"commands": [{"command": "completed", "exit_code": 0}]}),
        encoding="utf-8",
    )

    result = await EvalAgentPerformedAssertion().evaluate(
        _context(tmp_path), params
    )

    assert result.status == "failed"
    assert "launcher record" in result.message

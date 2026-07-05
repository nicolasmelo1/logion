from __future__ import annotations

import json

import pytest

from logion_agent_proving_ground.api_adapters.mock import MockApiAdapter
from logion_agent_proving_ground.artifacts import ArtifactStore
from logion_agent_proving_ground.assertions.registry import AssertionRegistry
from logion_agent_proving_ground.runner import (
    AgentDriverFactory,
    ScenarioRunner,
)
from logion_agent_proving_ground.scenarios.loader import load_scenario
from logion_agent_proving_ground.timeline import Timeline

COURSE_ID = "course_cli_workflow"
BOUNTY_ID = "bounty_exercise"


def _op(operation: str, **params: object) -> dict:
    return {"operation": operation, "params": params}


FULL_LOOP_OPERATIONS: dict[str, list] = {
    "creator_publishes_course": [
        _op(
            "publish_course",
            course_id=COURSE_ID,
            title="CLI Workflow",
            price_cents=500,
        ),
    ],
    "admin_approves_publication": [],
    "learner_buys_uses_reviews": [
        _op("purchase_course", course_id=COURSE_ID),
        _op("create_usage_report", course_id=COURSE_ID),
        _op("create_review", course_id=COURSE_ID, rating=5),
    ],
    "creator_opens_bounty": [
        _op("create_bounty", bounty_id=BOUNTY_ID, course_id=COURSE_ID),
    ],
    "learner_submits_bounty_work": [
        _op("submit_bounty", bounty_id=BOUNTY_ID),
    ],
    "creator_accepts_bounty": [
        _op("accept_bounty_submission", bounty_id=BOUNTY_ID),
    ],
    "admin_reviews_marketplace_state": [],
}


@pytest.fixture
def loop_runner_factory(tmp_path):
    def _make(operations: dict[str, list]):
        # marketplace_loop declares local-devrig, but the public test path
        # exercises the same scenario against the scripted/mock pair.
        scenario = load_scenario("builtin:marketplace_loop")
        for agent in scenario.agents:
            agent.driver = "scripted"
        api = MockApiAdapter(seed_course=False)
        drivers = AgentDriverFactory(
            scenario.driver_config,
            scripted_operations=operations,
            scripted_apply=lambda agent_id, op, params: api.record_operation(
                agent_id, op, **params
            ),
        )
        artifacts = ArtifactStore(tmp_path)
        timeline = Timeline(tmp_path / "timeline.jsonl")
        return ScenarioRunner(
            scenario=scenario,
            api=api,
            driver_factory=drivers,
            artifacts=artifacts,
            assertions=AssertionRegistry(),
            timeline=timeline,
            runs_root=tmp_path,
        )

    return _make


def _without(operations: dict[str, list], phase: str, op_name: str) -> dict:
    trimmed = {k: list(v) for k, v in operations.items()}
    trimmed[phase] = [
        op for op in trimmed[phase] if op.get("operation") != op_name
    ]
    return trimmed


async def test_marketplace_loop_passes_in_scripted_mock(
    loop_runner_factory,
) -> None:
    runner = loop_runner_factory(FULL_LOOP_OPERATIONS)
    result = await runner.run()
    assert result.status == "passed", result.failure_message
    phase_ids = [p["phase_id"] for p in result.phase_results]
    assert phase_ids == list(FULL_LOOP_OPERATIONS)


async def test_missing_purchase_fails(loop_runner_factory) -> None:
    operations = _without(
        FULL_LOOP_OPERATIONS, "learner_buys_uses_reviews", "purchase_course"
    )
    runner = loop_runner_factory(operations)
    result = await runner.run()
    assert result.status == "failed"
    failed_phase = result.phase_results[-1]
    assert failed_phase["phase_id"] == "learner_buys_uses_reviews"


async def test_missing_usage_report_fails(loop_runner_factory) -> None:
    operations = _without(
        FULL_LOOP_OPERATIONS,
        "learner_buys_uses_reviews",
        "create_usage_report",
    )
    runner = loop_runner_factory(operations)
    result = await runner.run()
    assert result.status == "failed"


async def test_duplicate_credit_debit_fails(loop_runner_factory) -> None:
    operations = {k: list(v) for k, v in FULL_LOOP_OPERATIONS.items()}
    operations["learner_buys_uses_reviews"] = [
        _op("purchase_course", course_id=COURSE_ID),
        *operations["learner_buys_uses_reviews"],
    ]
    runner = loop_runner_factory(operations)
    result = await runner.run()
    assert result.status == "failed"
    failed = [
        a
        for a in result.assertion_results
        if a.type == "api.no_double_credit_debit" and a.status == "failed"
    ]
    assert failed


async def test_optional_local_assertions_do_not_fail_mock_run(
    loop_runner_factory,
) -> None:
    runner = loop_runner_factory(FULL_LOOP_OPERATIONS)
    result = await runner.run()
    optional_types = {"logs.no_500s", "db.exact_credit_ledger"}
    outcomes = [
        a for a in result.assertion_results if a.type in optional_types
    ]
    assert outcomes
    assert all(a.status == "passed" for a in outcomes)
    assert result.status == "passed"


async def test_release_report_includes_timings_and_artifacts(
    loop_runner_factory, tmp_path
) -> None:
    runner = loop_runner_factory(FULL_LOOP_OPERATIONS)
    await runner.run()
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["artifact_root"] == str(tmp_path)
    for phase in report["phase_results"]:
        assert phase["started_at"]
        assert phase["finished_at"]
        assert phase["duration_seconds"] >= 0

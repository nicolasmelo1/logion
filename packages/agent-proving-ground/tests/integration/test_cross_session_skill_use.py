from __future__ import annotations

import pytest

from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.artifacts import ArtifactStore
from agent_proving_ground.assertions.registry import AssertionRegistry
from agent_proving_ground.cli import main
from agent_proving_ground.runner import (
    AgentDriverFactory,
    ScenarioRunner,
)
from agent_proving_ground.scenarios.loader import load_scenario
from agent_proving_ground.timeline import Timeline

COURSE_ID = "course_fixture"


def _op(operation: str, **params: object) -> dict:
    return {"operation": operation, "params": params}


CROSS_SESSION_OPERATIONS: dict[str, list] = {
    "buy_and_install": [
        _op("purchase_course", course_id=COURSE_ID),
    ],
    "fresh_session_use": [
        _op("create_usage_report", course_id=COURSE_ID),
        _op("create_review", course_id=COURSE_ID, rating=4),
    ],
}


@pytest.fixture
def cross_session_runner_factory(tmp_path):
    def _make(operations: dict[str, list]):
        scenario = load_scenario("builtin:cross_session_skill_use")
        api = MockApiAdapter()
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


def test_validate_builtin_cross_session_skill_use() -> None:
    assert main(["validate", "builtin:cross_session_skill_use"]) == 0


def test_fresh_session_does_not_prompt_for_usage_review() -> None:
    # The report contract must come from companion policy, never from the
    # visible prompt — same rule pinned for marketplace_loop.
    scenario = load_scenario("builtin:cross_session_skill_use")
    phase = next(p for p in scenario.phases if p.id == "fresh_session_use")
    visible_prompt = "\n".join(
        part for part in [phase.goal, phase.success_hint or ""] if part
    )
    assert "report-usage" not in visible_prompt
    assert "usage feedback" not in visible_prompt
    assert "review" not in visible_prompt.lower()
    assert any(a.type == "api.usage_report_exists" for a in phase.assertions)
    assert any(a.type == "api.review_exists" for a in phase.assertions)


def test_purchase_and_use_are_separate_sessions() -> None:
    # The scenario's premise: buying and using are distinct phases, so each
    # runs in a fresh driver session. Collapsing them back into one phase
    # would silently stop proving cross-session survival.
    scenario = load_scenario("builtin:cross_session_skill_use")
    phase_ids = [p.id for p in scenario.phases]
    assert phase_ids == ["buy_and_install", "fresh_session_use"]
    buy = scenario.phases[0]
    assert all(a.type != "api.usage_report_exists" for a in buy.assertions), (
        "usage must not be asserted in the purchasing session"
    )


async def test_cross_session_loop_passes(
    cross_session_runner_factory,
) -> None:
    runner = cross_session_runner_factory(CROSS_SESSION_OPERATIONS)
    result = await runner.run()
    assert result.status == "passed", result.failure_message
    phase_ids = [p["phase_id"] for p in result.phase_results]
    assert phase_ids == list(CROSS_SESSION_OPERATIONS)


async def test_missing_report_in_fresh_session_fails(
    cross_session_runner_factory,
) -> None:
    operations = {
        "buy_and_install": CROSS_SESSION_OPERATIONS["buy_and_install"],
        "fresh_session_use": [],
    }
    runner = cross_session_runner_factory(operations)
    result = await runner.run()
    assert result.status == "failed"


async def test_repurchase_in_fresh_session_fails_final_ledger(
    cross_session_runner_factory,
) -> None:
    # A fresh session that forgets its entitlement and buys the course again
    # must be caught by the final no-double-debit assertion.
    operations = {
        "buy_and_install": CROSS_SESSION_OPERATIONS["buy_and_install"],
        "fresh_session_use": [
            _op("purchase_course", course_id=COURSE_ID),
            *CROSS_SESSION_OPERATIONS["fresh_session_use"],
        ],
    }
    runner = cross_session_runner_factory(operations)
    result = await runner.run()
    assert result.status == "failed"

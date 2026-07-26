from __future__ import annotations

import json
from pathlib import Path

from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.artifacts import ArtifactStore
from agent_proving_ground.assertions.registry import AssertionRegistry
from agent_proving_ground.runner import AgentDriverFactory, ScenarioRunner
from agent_proving_ground.scenarios.loader import load_scenario
from agent_proving_ground.timeline import Timeline

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "resource_projection_backfill"
    / "fixture.json"
)


def _op(operation: str, **params: object) -> dict:
    return {"operation": operation, "params": params}


async def test_resource_projection_backfill_is_deterministic(tmp_path) -> None:
    scenario = load_scenario("builtin:resource_projection_backfill")
    # Hook paths are portable and relative to the configured devrig root. The
    # public checkout does not need to contain private operator boundaries.
    hook_paths_relative_to_devrig_root = {
        phase.local_hook for phase in scenario.phases if phase.local_hook
    }
    assert hook_paths_relative_to_devrig_root == {
        "scripts/devrig/backfill_resources.py"
    }
    for phase in scenario.phases:
        phase.local_hook = None
        phase.goal = "run the scripted scenario step"
    for agent in scenario.agents:
        agent.driver = "scripted"
    rerun = next(
        phase
        for phase in scenario.phases
        if phase.id == "operator-backfill-rerun"
    )
    fixture_snapshot = (
        "agent_skill:gh:phase-15-9/python-debugging-skill|"
        "course:course_python_debugging"
    )
    initial = next(
        phase for phase in scenario.phases if phase.id == "operator-backfill"
    )
    for assertion in initial.assertions:
        if assertion.type == "api.resource_backfill_applied":
            assertion.params = {
                "resources_created": 2,
                "projections_linked": 2,
                "identity_snapshot": fixture_snapshot,
            }
    for assertion in rerun.assertions:
        assertion.params = {
            "rerun_created": 0,
            "rerun_linked": 0,
            "before_identity_snapshot": fixture_snapshot,
            "after_identity_snapshot": fixture_snapshot,
        }
    fixture_canonicals = [
        "gh:phase-15-9/python-debugging-skill",
        "course:course_python_debugging",
    ]
    for assertion in [
        *(
            assertion
            for phase in scenario.phases
            for assertion in phase.assertions
        ),
        *scenario.final_assertions,
    ]:
        if assertion.type == "api.resource_search_returns_kinds":
            assertion.params["canonicals"] = fixture_canonicals

    api = MockApiAdapter(seed_course=False)
    api.seed_resource_fixture(json.loads(FIXTURE.read_text(encoding="utf-8")))
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "api.log").write_text(
        "GET /v1/resources 200\nPOST /v1/courses/purchase 200\n",
        encoding="utf-8",
    )
    operations = {
        "operator-backfill": [_op("backfill_resources")],
        "consumer-legacy-course-purchase": [_op("purchase_course")],
        "operator-backfill-rerun": [_op("backfill_resources")],
    }
    drivers = AgentDriverFactory(
        scenario.driver_config,
        scripted_operations=operations,
        scripted_apply=lambda agent_id, operation, params: (
            api.record_operation(agent_id, operation, **params)
        ),
    )
    runner = ScenarioRunner(
        scenario=scenario,
        api=api,
        driver_factory=drivers,
        artifacts=ArtifactStore(tmp_path),
        assertions=AssertionRegistry(),
        timeline=Timeline(tmp_path / "timeline.jsonl"),
        runs_root=tmp_path,
    )

    result = await runner.run()

    assert result.status == "passed", result.failure_message
    assert len(api._state.resources) == 2
    assert api._state.backfill_runs == [
        {"resources_created": 2, "projections_linked": 2},
        {"resources_created": 0, "projections_linked": 0},
    ]
    assert {outcome.type for outcome in result.assertion_results} >= {
        "logs.no_500s",
        "timeline.no_unredacted_secret",
        "api.resource_backfill_complete",
        "api.resource_backfill_applied",
        "api.resource_identity_unique",
        "api.resource_backfill_idempotent",
        "api.legacy_course_purchase_exists",
        "api.resource_search_returns_kinds",
    }
    search_outcomes = [
        outcome
        for outcome in result.assertion_results
        if outcome.type == "api.resource_search_returns_kinds"
    ]
    assert search_outcomes
    assert all(
        outcome.evidence["projection_kinds"]
        == ["indexed_listing", "published_course"]
        for outcome in search_outcomes
    )
    assert all(
        outcome.evidence["matched_canonicals"]
        == [
            "course:course_python_debugging",
            "gh:phase-15-9/python-debugging-skill",
        ]
        for outcome in search_outcomes
    )

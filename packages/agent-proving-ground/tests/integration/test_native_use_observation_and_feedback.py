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

RESOURCE_ID = "r1"
VERSION_ID = "v1"


def _op(operation: str, **params: object) -> dict:
    return {"operation": operation, "params": params}


NATIVE_FEEDBACK_OPERATIONS: dict[str, list] = {
    "install_and_use_in_xpto": [
        _op(
            "create_observation",
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            channel="npx_skills",
            scope_id="scope_xpto",
            repository="xpto",
        ),
        _op(
            "create_pending_usage",
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            repository="xpto",
        ),
        _op(
            "create_resource_feedback",
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            rating=4,
            acquisition_channel="npx_skills",
            installation_id="i1",
            task_class="software-development",
            body="Worked well for small reviews",
        ),
    ],
    "use_in_acme_no_leak": [
        _op(
            "create_observation",
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            channel="npx_skills",
            scope_id="scope_acme",
            repository="acme",
        ),
        _op(
            "create_pending_usage",
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            repository="acme",
        ),
    ],
    "submit_feedback_in_acme": [
        _op(
            "create_resource_feedback",
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            rating=3,
            acquisition_channel="npx_skills",
            installation_id="i2",
            task_class="software-development",
            body="Decent for basic reviews",
        ),
    ],
}


@pytest.fixture
def feedback_runner_factory(tmp_path):
    def _make(operations: dict[str, list]):
        scenario = load_scenario("builtin:native_use_observation_and_feedback")
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


def test_validate_builtin_native_use_observation_and_feedback() -> None:
    assert (
        main(["validate", "builtin:native_use_observation_and_feedback"]) == 0
    )


def test_scenario_has_two_repos_for_isolation() -> None:
    scenario = load_scenario("builtin:native_use_observation_and_feedback")
    phase_ids = [p.id for p in scenario.phases]
    assert "install_and_use_in_xpto" in phase_ids
    assert "use_in_acme_no_leak" in phase_ids
    assert "submit_feedback_in_acme" in phase_ids


def test_final_assertions_include_raw_observation_check() -> None:
    scenario = load_scenario("builtin:native_use_observation_and_feedback")
    types = [a.type for a in scenario.final_assertions]
    assert "api.raw_observation_not_uploaded" in types
    assert "timeline.no_unredacted_secret" in types


async def test_full_loop_passes(feedback_runner_factory) -> None:
    runner = feedback_runner_factory(NATIVE_FEEDBACK_OPERATIONS)
    result = await runner.run()
    assert result.status == "passed", result.failure_message
    phase_ids = [p["phase_id"] for p in result.phase_results]
    assert phase_ids == list(NATIVE_FEEDBACK_OPERATIONS)


async def test_missing_feedback_fails(feedback_runner_factory) -> None:
    operations = {
        "install_and_use_in_xpto": [
            *NATIVE_FEEDBACK_OPERATIONS["install_and_use_in_xpto"][:-1],
        ],
        "use_in_acme_no_leak": NATIVE_FEEDBACK_OPERATIONS[
            "use_in_acme_no_leak"
        ],
        "submit_feedback_in_acme": NATIVE_FEEDBACK_OPERATIONS[
            "submit_feedback_in_acme"
        ],
    }
    runner = feedback_runner_factory(operations)
    result = await runner.run()
    assert result.status == "failed"


async def test_idempotent_feedback_in_acme(feedback_runner_factory) -> None:
    operations = dict(NATIVE_FEEDBACK_OPERATIONS)
    operations["submit_feedback_in_acme"] = [
        _op(
            "create_resource_feedback",
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            rating=3,
            acquisition_channel="npx_skills",
            installation_id="i2",
            task_class="software-development",
            body="Decent for basic reviews",
        ),
        _op(
            "create_resource_feedback",
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            rating=3,
            acquisition_channel="npx_skills",
            installation_id="i2",
            task_class="software-development",
            body="Decent for basic reviews",
        ),
    ]
    runner = feedback_runner_factory(operations)
    result = await runner.run()
    assert result.status == "passed", result.failure_message

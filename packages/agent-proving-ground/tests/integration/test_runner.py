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


@pytest.fixture
def runner_factory(tmp_path):
    def _make(scenario_source, operations=None):
        scenario = load_scenario(scenario_source)
        api = MockApiAdapter()
        drivers = AgentDriverFactory(
            scenario.driver_config, scripted_operations=operations or {}
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


async def test_skill_report_contract_passes(runner_factory, tmp_path) -> None:
    runner = runner_factory(
        "builtin:skill_report_contract",
        operations={"use_course_and_report": ["create usage report"]},
    )
    runner.api.record_operation("learner", "create_usage_report")
    result = await runner.run()
    assert result.status == "passed"
    assert (tmp_path / "assertions-final.json").exists()
    timeline_lines = (
        (tmp_path / "timeline.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    assert json.loads(timeline_lines[-1])["type"] == "run.completed"


async def test_missing_usage_report_fails(runner_factory) -> None:
    runner = runner_factory("builtin:skill_report_contract")
    result = await runner.run()
    assert result.status == "failed"


async def test_unsupported_required_assertion_fails(
    runner_factory, tmp_path
) -> None:
    text = """
schema_version: "1"
name: unsupported_required
description: test
api_adapter: mock
agents:
  - id: a
    role: r
    driver: scripted
phases:
  - id: p
    actor: a
    goal: g
    assertions:
      - type: api.unsupported_assertion
"""
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(text, encoding="utf-8")
    runner = runner_factory(str(scenario_path))
    result = await runner.run()
    assert result.status == "failed"


async def test_unsupported_optional_assertion_does_not_fail(
    runner_factory, tmp_path
) -> None:
    text = """
schema_version: "1"
name: unsupported_optional
description: test
api_adapter: mock
agents:
  - id: a
    role: r
    driver: scripted
phases:
  - id: p
    actor: a
    goal: g
    assertions:
      - type: api.unsupported_assertion
        optional: true
"""
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(text, encoding="utf-8")
    runner = runner_factory(str(scenario_path))
    result = await runner.run()
    assert result.status == "passed"


async def test_multi_agent_scenario_uses_isolated_driver_instances(
    runner_factory,
    tmp_path,
) -> None:
    text = """
schema_version: "1"
name: multi_agent_isolation
description: test
api_adapter: mock
agents:
  - id: learner
    role: learner
    driver: scripted
    workspace: drafts
  - id: reviewer
    role: reviewer
    driver: scripted
phases:
  - id: learner_step
    actor: learner
    goal: learner goal
  - id: reviewer_step
    actor: reviewer
    goal: reviewer goal
"""
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(text, encoding="utf-8")
    runner = runner_factory(
        str(scenario_path),
        operations={
            "learner_step": ["draft answer"],
            "reviewer_step": ["review answer"],
        },
    )

    result = await runner.run()

    assert result.status == "passed"
    learner_transcript = (
        tmp_path / "agents" / "learner" / "drafts" / "transcript.md"
    ).read_text(encoding="utf-8")
    reviewer_transcript = (
        tmp_path / "agents" / "reviewer" / "workspace" / "transcript.md"
    ).read_text(encoding="utf-8")
    assert "learner goal" in learner_transcript
    assert "reviewer goal" not in learner_transcript
    assert "reviewer goal" in reviewer_transcript
    assert "learner goal" not in reviewer_transcript

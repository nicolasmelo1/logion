from __future__ import annotations

from pathlib import Path

from agent_proving_ground.api_adapters.base import ApiAdapter
from agent_proving_ground.artifacts import ArtifactStore
from agent_proving_ground.assertions.registry import AssertionRegistry
from agent_proving_ground.models import World
from agent_proving_ground.runner import AgentDriverFactory, ScenarioRunner
from agent_proving_ground.scenarios.schema import ScenarioSpec
from agent_proving_ground.timeline import Timeline


class DummyApiAdapter(ApiAdapter):
    name = "mock"

    async def start(self) -> None:
        return None

    async def create_world(
        self,
        run_id: str,
        scenario_name: str,
        agent_ids: list[str],
        agent_roles: dict[str, str] | None = None,
    ) -> World:
        del scenario_name, agent_ids, agent_roles
        return World(
            run_id=run_id,
            base_url="http://example.test",
            root_dir=Path("."),
        )

    async def snapshot(self, world: World) -> dict:
        del world
        return {}

    async def query(self, world: World, query: dict) -> dict:
        del world, query
        return {}

    async def stop(self) -> None:
        return None


async def test_local_hook_gets_package_pythonpath(tmp_path: Path) -> None:
    hook = tmp_path / "hook.py"
    hook.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "from agent_proving_ground._json import JsonObject\n"
        "print(json.dumps({'value': 'ok'}))\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)

    scenario = ScenarioSpec.model_validate({
        "name": "hook_pythonpath",
        "description": "test local hook pythonpath",
        "agents": [{"id": "agent1", "role": "tester"}],
        "phases": [
            {
                "id": "hook_phase",
                "actor": "agent1",
                "goal": "",
                "local_hook": str(hook),
                "local_hook_capture_json": {"VALUE": "value"},
            }
        ],
    })
    runner = ScenarioRunner(
        scenario=scenario,
        api=DummyApiAdapter(),
        driver_factory=AgentDriverFactory({}),
        artifacts=ArtifactStore(tmp_path / "artifacts"),
        assertions=AssertionRegistry(),
        timeline=Timeline(tmp_path / "timeline.jsonl"),
    )
    world = World(
        run_id="r1",
        base_url="http://example.test",
        root_dir=tmp_path,
        data={},
    )

    result = await runner._run_local_hook(scenario.phases[0], world)

    assert result["status"] == "completed"
    assert world.data["scenario_vars"]["VALUE"] == "ok"

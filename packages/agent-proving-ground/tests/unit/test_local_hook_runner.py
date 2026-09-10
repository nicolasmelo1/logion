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
        "kind": "rig",
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


def _teardown_scenario(hook: Path, marker: Path) -> ScenarioSpec:
    return ScenarioSpec.model_validate({
        "name": "teardown_runs",
        "description": "test teardown hooks",
        "kind": "rig",
        "agents": [{"id": "agent1", "role": "tester"}],
        "phases": [
            {"id": "phase1", "actor": "agent1", "goal": ""},
        ],
        "teardown_hooks": [
            {"hook": str(hook), "args": [str(marker)]},
        ],
    })


def _runner(scenario: ScenarioSpec, tmp_path: Path) -> ScenarioRunner:
    return ScenarioRunner(
        scenario=scenario,
        api=DummyApiAdapter(),
        driver_factory=AgentDriverFactory({}),
        artifacts=ArtifactStore(tmp_path / "artifacts"),
        assertions=AssertionRegistry(),
        timeline=Timeline(tmp_path / "timeline.jsonl"),
    )


async def test_teardown_hook_releases_what_the_run_started(
    tmp_path: Path,
) -> None:
    """The hook runs after the phases, without being a phase."""
    marker = tmp_path / "released"
    hook = tmp_path / "teardown.py"
    hook.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "open(sys.argv[1], 'w').write('down')\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    scenario = _teardown_scenario(hook, marker)
    runner = _runner(scenario, tmp_path)
    world = World(
        run_id="r1",
        base_url="http://example.test",
        root_dir=tmp_path,
        data={},
    )

    await runner._run_teardown_hooks(world)

    assert marker.read_text(encoding="utf-8") == "down"


async def test_a_failing_teardown_hook_does_not_raise(tmp_path: Path) -> None:
    """A teardown that fails must not give a scenario a second way to go red.

    The run's verdict was decided before this ran. Letting the release path
    raise would turn an operator's dirty machine into a failed measurement.
    """
    hook = tmp_path / "teardown.py"
    hook.write_text(
        "#!/usr/bin/env python3\nimport sys\nsys.exit(3)\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    scenario = _teardown_scenario(hook, tmp_path / "unused")
    runner = _runner(scenario, tmp_path)
    world = World(
        run_id="r1",
        base_url="http://example.test",
        root_dir=tmp_path,
        data={},
    )

    await runner._run_teardown_hooks(world)

    events = (tmp_path / "timeline.jsonl").read_text(encoding="utf-8")
    assert "run.teardown.completed" in events


async def test_no_world_means_nothing_was_started_to_release(
    tmp_path: Path,
) -> None:
    """A run that never built a world started nothing this can release."""
    marker = tmp_path / "released"
    hook = tmp_path / "teardown.py"
    hook.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "open(sys.argv[1], 'w').write('down')\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    runner = _runner(_teardown_scenario(hook, marker), tmp_path)

    await runner._run_teardown_hooks(None)

    assert not marker.exists()

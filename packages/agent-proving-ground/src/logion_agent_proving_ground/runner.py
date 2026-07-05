from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from logion_agent_proving_ground.api_adapters.base import ApiAdapter
from logion_agent_proving_ground.artifacts import ArtifactStore
from logion_agent_proving_ground.assertions.base import (
    AssertionContext,
    AssertionOutcome,
)
from logion_agent_proving_ground.assertions.registry import AssertionRegistry
from logion_agent_proving_ground.config import (
    DEFAULT_RUNS_ROOT,
    AssertionFailure,
    InconclusiveRun,
)
from logion_agent_proving_ground.drivers._provider import (
    ClaudeCodeDriver,
    CodexDriver,
    OpencodeDriver,
)
from logion_agent_proving_ground.drivers.base import AgentDriver, AgentLaunch
from logion_agent_proving_ground.drivers.local_process import (
    LocalProcessDriver,
)
from logion_agent_proving_ground.drivers.scripted import ScriptedDriver
from logion_agent_proving_ground.models import (
    ScenarioResult,
    World,
    utc_now_iso,
)
from logion_agent_proving_ground.scenarios.schema import (
    AgentSpec,
    PhaseSpec,
    ScenarioSpec,
)
from logion_agent_proving_ground.timeline import Timeline

_DRIVER_CLASSES: dict[str, type[AgentDriver]] = {
    "scripted": ScriptedDriver,
    "local-process": LocalProcessDriver,
    "opencode": OpencodeDriver,
    "codex": CodexDriver,
    "claude-code": ClaudeCodeDriver,
}


class AgentDriverFactory:
    def __init__(
        self,
        driver_config: dict[str, Any],
        *,
        scripted_operations: dict[str, list] | None = None,
        scripted_apply: Any = None,
        default_driver: str = "scripted",
    ) -> None:
        self._driver_config = driver_config
        self._scripted_operations = scripted_operations
        self._scripted_apply = scripted_apply
        self._default_driver = default_driver

    def get(self, agent_id: str, spec: AgentSpec) -> AgentDriver:
        name = spec.driver or self._default_driver
        cls = _DRIVER_CLASSES.get(name)
        if cls is None:
            raise InconclusiveRun(
                f"unknown driver {name} for agent {agent_id}"
            )
        if name == "local-process":
            return LocalProcessDriver(
                command=list(spec.command) if spec.command else None
            )
        if name == "scripted":
            return ScriptedDriver(
                operations=self._scripted_operations,
                apply_operation=self._scripted_apply,
            )
        if name in {"opencode", "codex", "claude-code"}:
            if name == "opencode":
                return OpencodeDriver(driver_config=self._driver_config)
            if name == "codex":
                return CodexDriver(driver_config=self._driver_config)
            return ClaudeCodeDriver(driver_config=self._driver_config)
        return cls()


class ScenarioRunner:
    def __init__(
        self,
        scenario: ScenarioSpec,
        api: ApiAdapter,
        driver_factory: AgentDriverFactory,
        artifacts: ArtifactStore,
        assertions: AssertionRegistry,
        timeline: Timeline,
        runs_root: Path | None = None,
        run_id: str | None = None,
    ) -> None:
        self.scenario = scenario
        self.api = api
        self.driver_factory = driver_factory
        self.artifacts = artifacts
        self.assertions = assertions
        self.timeline = timeline
        self.runs_root = runs_root or DEFAULT_RUNS_ROOT
        self.started_at = utc_now_iso()
        self.run_id = run_id or self._make_run_id()
        self._agents: dict[str, AgentDriver] = {}

    def _make_run_id(self) -> str:
        ts = self.started_at.replace(":", "").replace("-", "")
        return f"{ts[:15]}-{self.scenario.name}"

    async def run(self) -> ScenarioResult:
        result: ScenarioResult | None = None
        phase_results: list[dict] = []
        all_assertion_results: list[AssertionOutcome] = []
        self.timeline.event(
            "run.started", run_id=self.run_id, scenario=self.scenario.name
        )
        try:
            await self.api.start()
            self.timeline.event("api.started", api_adapter=self.api.name)
            world = await self.api.create_world(
                self.run_id,
                self.scenario.name,
                [a.id for a in self.scenario.agents],
                agent_roles={
                    a.id: a.devrig_role
                    for a in self.scenario.agents
                    if a.devrig_role
                },
            )
            self.timeline.event("world.created", world_base_url=world.base_url)
            await self._start_agents(world)
            for phase in self.scenario.phases:
                phase_result = await self._run_phase(phase, world)
                phase_results.append(phase_result)
                phase_assertions = phase_result.get("assertion_results", [])
                all_assertion_results.extend([
                    AssertionOutcome(**a) if isinstance(a, dict) else a
                    for a in phase_assertions
                ])
                if phase_result["status"] != "completed":
                    result = self._result(
                        status="failed",
                        failure_message=phase_result.get(
                            "message", "phase failed"
                        ),
                        assertion_results=all_assertion_results,
                        phase_results=phase_results,
                    )
                    break
            if result is None:
                final_assertion_results = await self._run_assertions(
                    self.scenario.final_assertions,
                    world,
                    phase_id=None,
                )
                all_assertion_results.extend(final_assertion_results)
                failed = [
                    a for a in final_assertion_results if a.status == "failed"
                ]
                run_status: Literal["passed", "failed"] = (
                    "failed" if failed else "passed"
                )
                result = self._result(
                    status=run_status,
                    assertion_results=all_assertion_results,
                    phase_results=phase_results,
                )
        except AssertionFailure as exc:
            result = self._result(status="failed", failure_message=str(exc))
        except InconclusiveRun as exc:
            result = self._result(
                status="inconclusive", failure_message=str(exc)
            )
        finally:
            if result is None:
                result = self._result(
                    status="inconclusive",
                    failure_message="run did not produce a result",
                )
            self.artifacts.write_json(
                "assertions.json",
                [r.model_dump(mode="json") for r in all_assertion_results],
            )
            self._write_report(result)
            self.timeline.event(
                "run.completed",
                run_id=self.run_id,
                status=result.status,
            )
            await self._stop_agents()
            await self.api.stop()
            await self.artifacts.flush()
            await self.timeline.flush()
            self.timeline.close()
        return result

    async def _start_agents(self, world: World) -> None:
        env_by_agent: dict[str, dict[str, str]] = {}
        for agent_spec in self.scenario.agents:
            driver = self.driver_factory.get(agent_spec.id, agent_spec)
            workspace_name = agent_spec.workspace or "workspace"
            workspace = self.artifacts.mkdir(
                f"agents/{agent_spec.id}/{workspace_name}"
            )
            env = {**agent_spec.env, **world.agent_env.get(agent_spec.id, {})}
            env_by_agent[agent_spec.id] = env
            launch = AgentLaunch(
                run_id=self.run_id,
                agent_id=agent_spec.id,
                role=agent_spec.role,
                workspace=workspace,
                env=env,
                system_prompt=agent_spec.system_prompt,
                timeout_seconds=agent_spec.timeout_seconds,
            )
            await driver.start(launch)
            self._agents[agent_spec.id] = driver
            self.timeline.event(
                "agent.started",
                agent_id=agent_spec.id,
                driver=driver.name,
                workspace=str(workspace),
            )
        self.artifacts.write_json("environment.json", env_by_agent)

    async def _run_phase(self, phase: PhaseSpec, world: World) -> dict:
        import time

        phase_started_at = utc_now_iso()
        phase_clock = time.monotonic()

        def _timed(result: dict) -> dict:
            result["started_at"] = phase_started_at
            result["finished_at"] = utc_now_iso()
            result["duration_seconds"] = round(
                time.monotonic() - phase_clock, 3
            )
            return result

        self.timeline.event("phase.started", phase_id=phase.id)
        driver = self._agents.get(phase.actor)
        if driver is None:
            return _timed({
                "phase_id": phase.id,
                "status": "failed",
                "message": "actor not found",
            })
        self.timeline.event(
            "agent.goal.sent",
            phase_id=phase.id,
            agent_id=phase.actor,
            goal=phase.goal,
        )
        turn = await driver.send_goal(
            phase_id=phase.id,
            goal=phase.goal,
            success_hint=phase.success_hint,
            timeout_seconds=phase.timeout_seconds,
        )
        self.timeline.event(
            "agent.turn.completed",
            phase_id=phase.id,
            agent_id=phase.actor,
            status=turn.status,
            summary=turn.summary,
        )
        if turn.status != "completed":
            return _timed({
                "phase_id": phase.id,
                "status": turn.status,
                "message": f"agent turn {turn.status} for phase {phase.id}",
            })
        snapshot = await self.api.snapshot(world)
        self.artifacts.write_json(f"snapshots/after-{phase.id}.json", snapshot)
        assertion_results = await self._run_assertions(
            phase.assertions,
            world,
            phase_id=phase.id,
        )
        failed = [a for a in assertion_results if a.status == "failed"]
        status = "failed" if failed else "completed"
        self.timeline.event(
            "phase.completed",
            phase_id=phase.id,
            status=status,
        )
        return _timed({
            "phase_id": phase.id,
            "status": status,
            "assertion_results": [
                a.model_dump(mode="json") for a in assertion_results
            ],
        })

    async def _run_assertions(
        self,
        assertions: list,
        world: World,
        phase_id: str | None,
    ) -> list:
        results = []
        for assertion_spec in assertions:
            ctx = AssertionContext(
                scenario_name=self.scenario.name,
                phase_id=phase_id,
                world=world,
                api=self.api,
                artifacts_dir=self.artifacts.root,
                timeline=self.timeline,
            )
            outcome = await self.assertions.evaluate(
                ctx,
                assertion_spec.type,
                assertion_spec.params,
            )
            if outcome.status == "unsupported" and assertion_spec.optional:
                outcome = AssertionOutcome(
                    type=assertion_spec.type,
                    status="passed",
                    message=(
                        f"optional assertion skipped: {assertion_spec.type}"
                    ),
                    evidence={},
                )
            elif outcome.status == "unsupported":
                outcome = AssertionOutcome(
                    type=assertion_spec.type,
                    status="failed",
                    message=(
                        "unsupported required assertion: "
                        f"{assertion_spec.type}"
                    ),
                    evidence={},
                )
            self.timeline.event(
                "assertion.completed",
                phase_id=phase_id,
                type=assertion_spec.type,
                status=outcome.status,
            )
            results.append(outcome)
        self.artifacts.write_json(
            f"assertions{f'-{phase_id}' if phase_id else '-final'}.json",
            [r.model_dump(mode="json") for r in results],
        )
        return results

    def _result(
        self,
        *,
        status: Literal["passed", "failed", "inconclusive"],
        failure_message: str | None = None,
        assertion_results: list | None = None,
        phase_results: list | None = None,
    ) -> ScenarioResult:
        return ScenarioResult(
            run_id=self.run_id,
            scenario=self.scenario.name,
            status=status,
            api_adapter=self.api.name,
            agent_drivers={aid: d.name for aid, d in self._agents.items()},
            started_at=self.started_at,
            finished_at=utc_now_iso(),
            phase_results=phase_results or [],
            assertion_results=assertion_results or [],
            artifact_root=self.artifacts.root,
            failure_message=failure_message,
        )

    def _write_report(self, result: ScenarioResult) -> None:
        report = {
            "run_id": result.run_id,
            "scenario": result.scenario,
            "status": result.status,
            "api_adapter": result.api_adapter,
            "agent_drivers": result.agent_drivers,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "phase_results": result.phase_results,
            "assertion_results": [
                a.model_dump(mode="json") for a in result.assertion_results
            ],
            "failure_message": result.failure_message,
            "artifact_root": str(result.artifact_root),
        }
        self.artifacts.write_json("report.json", report)

    async def _stop_agents(self) -> None:
        for driver in self._agents.values():
            await driver.stop()
        self._agents.clear()

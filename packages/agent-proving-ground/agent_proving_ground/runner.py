from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal, overload

from agent_proving_ground._json import (
    JsonObject,
    JsonValue,
    child,
    children,
    opt_str,
)
from agent_proving_ground.api_adapters.base import ApiAdapter
from agent_proving_ground.artifacts import ArtifactStore
from agent_proving_ground.assertions.base import (
    AssertionContext,
    AssertionOutcome,
)
from agent_proving_ground.assertions.registry import AssertionRegistry
from agent_proving_ground.config import (
    DEFAULT_RUNS_ROOT,
    AssertionFailure,
    InconclusiveRun,
)
from agent_proving_ground.drivers._provider import (
    ClaudeCodeDriver,
    CodexDriver,
    OpencodeDriver,
)
from agent_proving_ground.drivers.base import AgentDriver, AgentLaunch
from agent_proving_ground.drivers.hermes import HermesDriver
from agent_proving_ground.drivers.local_process import (
    LocalProcessDriver,
)
from agent_proving_ground.drivers.scripted import (
    ApplyOperation,
    ScriptedDriver,
)
from agent_proving_ground.models import (
    ScenarioResult,
    World,
    utc_now_iso,
)
from agent_proving_ground.scenarios.schema import (
    AgentSpec,
    AssertionSpec,
    PhaseSpec,
    ScenarioSpec,
)
from agent_proving_ground.timeline import Timeline

_DRIVER_CLASSES: dict[str, type[AgentDriver]] = {
    "scripted": ScriptedDriver,
    "local-process": LocalProcessDriver,
    "opencode": OpencodeDriver,
    "codex": CodexDriver,
    "claude-code": ClaudeCodeDriver,
    "hermes": HermesDriver,
}

_PARAMETER_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
_SENSITIVE_BINDING_RE = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|AUTH|API_KEY|PRIVATE_KEY)", re.IGNORECASE
)
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _extract_last_json(stdout: str) -> JsonObject | None:
    """Find the last JSON object printed by a local hook."""
    finder = _JsonFinder()
    return finder.last_object(stdout)


class _JsonFinder:
    """Backward scanner for the last JSON object in a text string.

    Used to capture non-secret output from local phase hooks."""

    @staticmethod
    def last_object(text: str) -> JsonObject | None:
        depth = 0
        end: int | None = None
        for idx in range(len(text) - 1, -1, -1):
            char = text[idx]
            if char == "}":
                if depth == 0:
                    end = idx
                depth += 1
            elif char == "{":
                if depth == 1 and end is not None:
                    try:
                        return json.loads(text[idx : end + 1])
                    except ValueError:
                        end = None
                        depth = 0
                        continue
                depth = max(0, depth - 1)
        return None


def _resolve_hook_path(hook: str, devrig_root: Path) -> str:
    """Resolve a relative ``local_hook`` against the roots that can own it.

    A scenario's hook may live beside the scenario in this package or in the
    workspace that owns the dev rig, and ``--devrig-root`` legitimately
    points at either. Resolving only against the devrig root makes a
    scenario runnable from one checkout and not the other, which surfaces
    as a bare FileNotFoundError halfway into a run.
    """
    candidates = [devrig_root / hook]
    public_repo = os.environ.get("LOGION_PUBLIC_REPO_PATH")
    if public_repo:
        candidates.append(Path(public_repo) / hook)
    # The repo that ships this package, so a scenario bundled here always
    # finds its own hook no matter which root the run was pointed at.
    candidates.append(Path(__file__).resolve().parents[3] / hook)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return str(candidates[0])


def _scenario_bindings(world: World) -> dict[str, str]:
    bindings = {
        key: value
        for key, value in os.environ.items()
        if not _SENSITIVE_BINDING_RE.search(key)
    }
    bindings.update({
        key: str(value)
        for key, value in (world.data or {}).items()
        if isinstance(value, (str, int, float))
        and not _SENSITIVE_BINDING_RE.search(key)
    })
    scenario_vars = (world.data or {}).get("scenario_vars")
    if isinstance(scenario_vars, dict):
        bindings.update({
            str(key): str(value)
            for key, value in scenario_vars.items()
            if not _SENSITIVE_BINDING_RE.search(str(key))
        })
    return bindings


@overload
def _resolve_scenario_value(value: str, bindings: dict[str, str]) -> str: ...


@overload
def _resolve_scenario_value(
    value: JsonObject, bindings: dict[str, str]
) -> JsonObject: ...


@overload
def _resolve_scenario_value(
    value: list[JsonObject], bindings: dict[str, str]
) -> list[JsonObject]: ...


@overload
def _resolve_scenario_value(
    value: JsonValue, bindings: dict[str, str]
) -> JsonValue: ...


def _resolve_scenario_value(
    value: JsonValue, bindings: dict[str, str]
) -> JsonValue:
    """Substitute ``${param}`` bindings throughout a scenario value.

    Overloaded because the substitution is shape-preserving: a mapping
    stays a mapping, a string stays a string. Without that, every
    caller would have to re-narrow a value whose shape it already knew.
    """
    if isinstance(value, dict):
        return {
            key: _resolve_scenario_value(item, bindings)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_resolve_scenario_value(item, bindings) for item in value]
    if not isinstance(value, str):
        return value

    missing = sorted(set(_PARAMETER_RE.findall(value)) - bindings.keys())
    if missing:
        names = ", ".join(missing)
        raise InconclusiveRun(f"unresolved scenario parameters: {names}")
    return _PARAMETER_RE.sub(lambda match: bindings[match.group(1)], value)


class AgentDriverFactory:
    def __init__(
        self,
        driver_config: JsonObject,
        *,
        scripted_operations: dict[str, list] | None = None,
        scripted_apply: ApplyOperation | None = None,
        default_driver: str | None = None,
    ) -> None:
        self._driver_config = driver_config
        self._scripted_operations = scripted_operations
        self._scripted_apply = scripted_apply
        self._default_driver = default_driver

    def configured_model(self, driver_name: str) -> str | None:
        provider_cfg = child(self._driver_config, driver_name)
        return opt_str(provider_cfg, "model") or None

    def get(self, agent_id: str, spec: AgentSpec) -> AgentDriver:
        name = self._default_driver or spec.driver or "scripted"
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
        if name == "hermes":
            return HermesDriver(driver_config=self._driver_config)
        return cls()


#: ``logion`` stand-in placed on an agent's PATH. A harness hook inherits
#: the harness environment, so the bare command the integration installed
#: has to resolve there. Observe invocations are teed to ``RECORDS`` before
#: reaching the real CLI so their provenance can be asserted afterwards.
_CLI_SHIM = """#!/bin/sh
# Written by agent-proving-ground. Not a packaging artifact: it wraps the
# CLI the rig already installed so the payload a harness delivers can be
# recorded, and execs that same binary for everything else.
set -eu
CLI="{cli}"
RECORDS="{records}"
if [ "${{1:-}}" = "usage" ] && [ "${{2:-}}" = "observe" ]; then
    mkdir -p "$RECORDS"
    stem="$RECORDS/$$-$(od -An -N4 -tx1 /dev/urandom | tr -d ' ')"
    cat > "$stem.stdin.json"
    printf '%s\n' "$*" > "$stem.argv"
    set +e
    # `--json` is appended for capture only. The installed hook does not
    # pass it, and without it observe renders human lines no assertion can
    # check. Same code path, same spool write.
    "$CLI" "$@" --json < "$stem.stdin.json" > "$stem.stdout.json"
    status=$?
    set -e
    # A harness fires the hook on every matching tool call, so most
    # responses are `ignored`. Name the one that actually recorded an
    # observation: that is the response the assertions are about.
    if grep -q '"disposition"[[:space:]]*:[[:space:]]*"recorded"' \\
        "$stem.stdout.json" 2>/dev/null; then
        cp "$stem.stdin.json" "$RECORDS/recorded.stdin.json"
        cp "$stem.stdout.json" "$RECORDS/recorded.stdout.json"
    fi
    cat "$stem.stdout.json"
    exit "$status"
fi
exec "$CLI" "$@"
"""


def _cli_cannot_observe(cli: str | None) -> str | None:
    """Reason *cli* cannot record an observation, or ``None`` if it can.

    The rig installs a built wheel, so the CLI on an agent's PATH can
    predate the command a harness hook calls. That failure is worth naming:
    without it the run looks like a harness that never fired its hook,
    which is the same symptom as a genuinely broken integration.
    """
    if not cli:
        return None
    probe = subprocess.run(
        [cli, "usage", "observe", "--help"],
        capture_output=True,
        check=False,
    )
    if probe.returncode == 0:
        return None
    return (
        f"{cli} does not support `usage observe` — the installed artifact "
        "predates it; rebuild it (make dev-rebuild-cli) before a run that "
        "has to observe"
    )


def _strip_all_logion_dirs(path_value: str) -> str:
    """Drop every PATH entry that exposes a ``logion`` binary.

    An agent declared ``logion_cli: false`` must not be able to reach the CLI
    at all. Asking it not to in the goal is a different guarantee: the agent
    can comply with the prose and still resolve a CLI the rig left there.
    """
    if not path_value:
        return path_value
    kept: list[str] = []
    for entry in path_value.split(os.pathsep):
        if not entry:
            continue
        if (Path(entry) / "logion").exists():
            continue
        kept.append(entry)
    return os.pathsep.join(kept)


def _strip_shadowed_logion_dirs(
    path_value: str, preferred_cli: str | None
) -> str:
    """Remove PATH entries that expose the wrong `logion` binary.

    The proving ground chooses one installed CLI artifact per agent. If a
    later PATH segment also contains a `logion` binary (for example an old
    global pipx install), some provider shell tools may still resolve that
    stale binary. Keep the preferred entry and drop conflicting later ones
    only.
    """
    if not path_value or not preferred_cli:
        return path_value
    try:
        preferred = Path(preferred_cli).resolve()
    except OSError:
        return path_value
    kept: list[str] = []
    for entry in path_value.split(os.pathsep):
        if not entry:
            continue
        candidate = Path(entry) / "logion"
        try:
            if candidate.exists() and candidate.resolve() != preferred:
                continue
        except OSError:
            pass
        kept.append(entry)
    return os.pathsep.join(kept)


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
            self._validate_execution_requirements()
            for phase in self.scenario.phases:
                try:
                    phase_result = await self._run_phase(phase, world)
                except InconclusiveRun as exc:
                    phase_result = {
                        "phase_id": phase.id,
                        "status": "inconclusive",
                        "message": str(exc),
                    }
                phase_results.append(phase_result)
                all_assertion_results.extend(
                    AssertionOutcome.model_validate(entry)
                    for entry in children(phase_result, "assertion_results")
                )
                if phase_result["status"] != "completed":
                    run_status_for_phase: Literal[
                        "passed", "failed", "inconclusive"
                    ] = (
                        "inconclusive"
                        if phase_result["status"] == "inconclusive"
                        else "failed"
                    )
                    result = self._result(
                        status=run_status_for_phase,
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

    def _validate_execution_requirements(self) -> None:
        requirements = self.scenario.execution_requirements
        if (
            requirements.api_adapters
            and self.api.name not in requirements.api_adapters
        ):
            allowed = ", ".join(requirements.api_adapters)
            raise InconclusiveRun(
                f"scenario requires API adapter in [{allowed}], "
                f"got {self.api.name}"
            )
        for agent_id, driver in self._agents.items():
            if (
                requirements.agent_drivers
                and driver.name not in requirements.agent_drivers
            ):
                allowed = ", ".join(requirements.agent_drivers)
                raise InconclusiveRun(
                    f"scenario requires agent driver in [{allowed}], "
                    f"got {driver.name} for {agent_id}"
                )
            allowed_models = requirements.driver_models.get(driver.name, [])
            if allowed_models:
                model = self.driver_factory.configured_model(driver.name)
                if model not in allowed_models:
                    allowed = ", ".join(allowed_models)
                    raise InconclusiveRun(
                        f"scenario requires {driver.name} model in "
                        f"[{allowed}], got {model or 'unset'}"
                    )

    def _write_cli_shim(
        self, agent_id: str, *, cli: str, invocations: Path
    ) -> Path:
        """Wrap *cli* as ``logion`` for *agent_id*; return the wrapper dir.

        ``integrations enable`` writes the hook command as a bare
        ``logion usage observe``, so the harness needs that name on PATH.
        The api adapter already puts the rig's installed CLI there; this
        wrapper shadows it only to keep a copy of the payload, and execs
        the same binary. Wrapping the installed artifact rather than the
        source checkout keeps the run honest about what a user has.

        The recorded payload is what separates an observation the harness
        delivered from one an agent typed, which is the difference between
        proving the loop and asserting it.
        """
        bin_dir = self.artifacts.mkdir(f"agents/{agent_id}/bin")
        shim_path = bin_dir / "logion"
        shim_path.write_text(
            _CLI_SHIM.format(cli=cli, records=invocations),
            encoding="utf-8",
        )
        shim_path.chmod(0o755)
        return bin_dir

    async def _start_agents(self, world: World) -> None:
        env_by_agent: dict[str, dict[str, str]] = {}
        for agent_spec in self.scenario.agents:
            driver = self.driver_factory.get(agent_spec.id, agent_spec)
            workspace_name = agent_spec.workspace or "workspace"
            workspace = self.artifacts.mkdir(
                f"agents/{agent_spec.id}/{workspace_name}"
            )
            scenario_vars = world.data.setdefault("scenario_vars", {})
            if not isinstance(scenario_vars, dict):
                raise InconclusiveRun("world scenario_vars is not a mapping")
            prefix = (
                "AGENT_" + re.sub(r"[^A-Za-z0-9]", "_", agent_spec.id).upper()
            )
            logion_home = self.artifacts.mkdir(
                f"agents/{agent_spec.id}/logion-home"
            )
            invocations = self.artifacts.mkdir(
                f"agents/{agent_spec.id}/hook-invocations"
            )
            scenario_vars[f"{prefix}_WORKSPACE"] = str(workspace)
            scenario_vars[f"{prefix}_LOGION_HOME"] = str(logion_home)
            scenario_vars[f"{prefix}_HOOK_INVOCATIONS"] = str(invocations)
            if driver.name == "codex":
                (workspace / ".agents" / "skills").mkdir(
                    parents=True, exist_ok=True
                )
                (workspace / ".codex").mkdir(parents=True, exist_ok=True)
            # The goal text needs the harness that is actually driving the
            # run, not the one the scenario declared: ``--agent-driver``
            # replaces every agent's driver, and a hook installed for the
            # wrong harness can never fire.
            scenario_vars[f"{prefix}_HARNESS"] = driver.name
            scenario_vars["LOGION_PUBLIC_REPO_PATH"] = str(world.root_dir)
            env = {**agent_spec.env, **world.agent_env.get(agent_spec.id, {})}
            env["LOGION_PUBLIC_REPO_PATH"] = str(world.root_dir)
            env["LOGION_AGENT_WORKSPACE"] = str(workspace)
            # A harness hook is a subprocess of the harness, so the bare
            # ``logion`` that ``integrations enable`` writes has to resolve
            # in this environment. The api adapter is what knows where the
            # installed CLI lives; all this does is shadow it with a
            # recording wrapper so the delivered payload can be asserted on.
            # LOGION_HOME is per agent on purpose. Two agents can share one
            # devrig role — that is how the isolation phase is written — so
            # the role home cannot also be the state under test. Server auth
            # travels in LOGION_API_KEY, not in this directory, so a fresh
            # one costs nothing and keeps the two agents genuinely separate.
            env["LOGION_HOME"] = str(logion_home)
            if not agent_spec.logion_cli:
                env["PATH"] = _strip_all_logion_dirs(
                    env.get("PATH", os.environ.get("PATH", ""))
                )
            installed_cli = shutil.which("logion", path=env.get("PATH"))
            # A local hook that has to run the CLI needs the same artifact
            # the agent has, and it cannot find it: the role-tree PATH lives
            # in the adapter's per-agent env, not in the runner's own. The
            # unshimmed path is deliberate — the shim exists to record
            # observations, and a hook doing bookkeeping is not observing.
            # Bound even when empty: an unresolved ``${...}`` fails the run
            # as "unresolved scenario parameters", which says nothing about
            # a missing CLI. The hook that reads it explains that instead.
            scenario_vars[f"{prefix}_LOGION_CLI"] = installed_cli or ""
            # Hooks get non-secret bindings only, so the base URL has to
            # travel as one; it comes from the devrig env file, which a hook
            # would otherwise have to parse (and which holds secrets).
            scenario_vars["LOGION_API_BASE_URL"] = world.base_url
            # The resolved role, not the declared one: ``--devrig-role``
            # can replace it, and a hook authenticating as the wrong role
            # would reconcile against a catalog the agent never saw.
            scenario_vars[f"{prefix}_DEVRIG_ROLE"] = env.get(
                "LOGION_DEVRIG_ROLE", agent_spec.devrig_role or ""
            )
            reason = _cli_cannot_observe(installed_cli)
            if installed_cli and reason is None:
                env["PATH"] = _strip_shadowed_logion_dirs(
                    env.get("PATH", os.environ.get("PATH", "")),
                    installed_cli,
                )
                bin_dir = self._write_cli_shim(
                    agent_spec.id,
                    cli=installed_cli,
                    invocations=invocations,
                )
                env["PATH"] = os.pathsep.join((
                    str(bin_dir),
                    env.get("PATH", os.environ.get("PATH", "")),
                ))
            else:
                # Not fatal here: most scenarios never observe, and the
                # observation assertions fail on their own. But say why in
                # the timeline, because a silent skip is exactly how a
                # replay becomes the only path a gate can take.
                self.timeline.event(
                    "agent.cli_wrapper_skipped",
                    agent_id=agent_spec.id,
                    cli=installed_cli or "",
                    reason=reason or "no logion on the agent PATH",
                )
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

    def _validate_scenario_parameters(self, world: World) -> None:
        bindings = _scenario_bindings(world)
        for phase in self.scenario.phases:
            _resolve_scenario_value(phase.goal, bindings)
            _resolve_scenario_value(phase.success_hint, bindings)
            _resolve_scenario_value(phase.local_hook_args, bindings)
            phase_bindings = dict(bindings)
            if phase.local_hook:
                for name in phase.local_hook_capture_json:
                    phase_bindings.setdefault(name, name)
            for assertion in phase.assertions:
                _resolve_scenario_value(assertion.params, phase_bindings)
        for assertion in self.scenario.final_assertions:
            _resolve_scenario_value(assertion.params, bindings)

    def _available_bindings(self, world: World) -> dict[str, str]:
        """Return bindings including placeholders for capture variables."""
        bindings = _scenario_bindings(world)
        for phase in self.scenario.phases:
            for assertion in phase.assertions:
                for name in assertion.capture:
                    bindings.setdefault(name, name)
            for name in phase.local_hook_capture_json:
                bindings.setdefault(name, name)
        for assertion in self.scenario.final_assertions:
            for name in assertion.capture:
                bindings.setdefault(name, name)
        return bindings

    async def _run_phase(self, phase: PhaseSpec, world: World) -> dict:
        import time

        phase_started_at = utc_now_iso()
        phase_clock = time.monotonic()
        available_bindings = self._available_bindings(world)

        def _timed(result: dict) -> dict:
            result["started_at"] = phase_started_at
            result["finished_at"] = utc_now_iso()
            result["duration_seconds"] = round(
                time.monotonic() - phase_clock, 3
            )
            return result

        self.timeline.event("phase.started", phase_id=phase.id)
        bindings = _scenario_bindings(world)
        if phase.local_hook:
            hook_result = await self._run_local_hook(phase, world)
            if hook_result["status"] != "completed":
                return _timed({
                    "phase_id": phase.id,
                    "status": hook_result["status"],
                    "message": hook_result["message"],
                })
            # Re-bind now that the hook may have populated scenario_vars.
            bindings = _scenario_bindings(world)
            captured_vars = child(hook_result, "captured_vars")
            if captured_vars:
                scenario_vars = world.data.setdefault("scenario_vars", {})
                if not isinstance(scenario_vars, dict):
                    return _timed({
                        "phase_id": phase.id,
                        "status": "failed",
                        "message": "world scenario_vars is not a mapping",
                    })
                for name, value in captured_vars.items():
                    scenario_vars[name] = value
                    bindings[name] = str(value)
                world.data["scenario_vars"] = scenario_vars
        driver = self._agents.get(phase.actor)
        if driver is None and phase.goal.strip():
            return _timed({
                "phase_id": phase.id,
                "status": "failed",
                "message": "actor not found",
            })
        if not phase.goal.strip():
            snapshot = await self.api.snapshot(world)
            self.artifacts.write_json(
                f"snapshots/after-{phase.id}.json", snapshot
            )
            resolved_assertions = _resolve_scenario_value(
                [a.model_dump(mode="json") for a in phase.assertions], bindings
            )
            assertion_results = await self._run_assertions(
                resolved_assertions,
                world,
                phase_id=phase.id,
                already_resolved=True,
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
        goal = _resolve_scenario_value(phase.goal, available_bindings)
        success_hint = (
            _resolve_scenario_value(phase.success_hint, available_bindings)
            if phase.success_hint is not None
            else None
        )
        self.timeline.event(
            "agent.goal.sent",
            phase_id=phase.id,
            agent_id=phase.actor,
            goal=goal,
        )
        assert driver is not None
        turn = await driver.send_goal(
            phase_id=phase.id,
            goal=goal,
            success_hint=success_hint,
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

    def _capture_assertion_outputs(
        self,
        *,
        capture: dict[str, str],
        outcome: AssertionOutcome,
        world: World,
    ) -> AssertionOutcome:
        if not capture or outcome.status != "passed":
            return outcome
        missing = [
            evidence_key
            for evidence_key in capture.values()
            if outcome.evidence.get(evidence_key) is None
        ]
        if missing:
            return AssertionOutcome(
                type=outcome.type,
                status="failed",
                message=(
                    "assertion capture missing evidence: "
                    + ", ".join(sorted(missing))
                ),
                evidence=outcome.evidence,
            )
        scenario_vars = world.data.setdefault("scenario_vars", {})
        if not isinstance(scenario_vars, dict):
            return AssertionOutcome(
                type=outcome.type,
                status="failed",
                message="world scenario_vars is not a mapping",
                evidence=outcome.evidence,
            )
        for name, evidence_key in capture.items():
            scenario_vars[name] = outcome.evidence[evidence_key]
        return outcome

    async def _run_assertions(
        self,
        assertions: list,
        world: World,
        phase_id: str | None,
        *,
        already_resolved: bool = False,
    ) -> list:
        results = []
        for assertion_spec in assertions:
            if isinstance(assertion_spec, dict):
                assertion_spec = AssertionSpec.model_validate(assertion_spec)
            ctx = AssertionContext(
                scenario_name=self.scenario.name,
                phase_id=phase_id,
                world=world,
                api=self.api,
                artifacts_dir=self.artifacts.root,
                timeline=self.timeline,
            )
            params = (
                assertion_spec.params
                if already_resolved
                else _resolve_scenario_value(
                    assertion_spec.params, _scenario_bindings(world)
                )
            )
            outcome = await self.assertions.evaluate(
                ctx,
                assertion_spec.type,
                params,
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
            outcome = self._capture_assertion_outputs(
                capture=assertion_spec.capture,
                outcome=outcome,
                world=world,
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

    async def _run_local_hook(
        self, phase: PhaseSpec, world: World
    ) -> JsonObject:
        """Execute a local, non-agent phase hook and capture public JSON.

        The hook command runs inside the public repo root so workspace
        scripts (``make dev-setup-handoff``, etc.) are discoverable. It
        receives only non-secret scenario bindings in its environment.
        Captured keys are written into ``world.data["scenario_vars"]``
        before the phase assertions run.
        """
        import asyncio
        import subprocess

        hook = os.path.expandvars(str(phase.local_hook))
        self.timeline.event(
            "phase.local_hook.started",
            phase_id=phase.id,
            hook=hook,
        )
        if not hook.startswith("/"):
            hook = _resolve_hook_path(hook, world.root_dir)
        bindings = _scenario_bindings(world)
        args = [
            _resolve_scenario_value(a, bindings) if isinstance(a, str) else a
            for a in phase.local_hook_args
        ]
        args = [os.path.expandvars(str(a)) for a in args]
        hook_path = Path(hook)
        cmd = [hook, *args]
        if hook_path.suffix == ".py":
            cmd = [sys.executable, hook, *args]
        pythonpath_entries: list[str] = []
        env_pythonpath = os.environ.get("PYTHONPATH", "")
        if env_pythonpath:
            pythonpath_entries.extend(
                entry for entry in env_pythonpath.split(os.pathsep) if entry
            )
        package_root_str = str(_PACKAGE_ROOT)
        if package_root_str not in pythonpath_entries:
            pythonpath_entries.insert(0, package_root_str)
        env = {
            **os.environ,
            **bindings,
            "LOGION_PUBLIC_REPO_PATH": str(world.root_dir),
            "PYTHONPATH": os.pathsep.join(pythonpath_entries),
        }
        env.pop("LOGION_API_KEY", None)
        env.pop("LOGION_PROVING_GROUND_API_KEY", None)
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                cmd,
                cwd=world.root_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=phase.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "message": f"local hook {phase.id} timed out",
            }
        if proc.returncode != 0:
            return {
                "status": "failed",
                "message": (
                    f"local hook {phase.id} exited {proc.returncode}: "
                    f"{proc.stderr[:500]}"
                ),
            }
        stdout_tail = _extract_last_json(proc.stdout)
        if stdout_tail is None:
            return {
                "status": "failed",
                "message": f"local hook {phase.id} produced no JSON object",
            }
        scenario_vars = world.data.setdefault("scenario_vars", {})
        if not isinstance(scenario_vars, dict):
            return {
                "status": "failed",
                "message": "world scenario_vars is not a mapping",
            }
        missing = []
        for name, key in phase.local_hook_capture_json.items():
            if key not in stdout_tail:
                missing.append(key)
                continue
            scenario_vars[name] = stdout_tail[key]
        world.data["scenario_vars"] = scenario_vars
        if missing:
            return {
                "status": "failed",
                "message": (
                    "local hook capture missing keys: "
                    + ", ".join(sorted(missing))
                ),
            }
        self.timeline.event(
            "phase.local_hook.completed",
            phase_id=phase.id,
            captured=list(phase.local_hook_capture_json.keys()),
        )
        return {
            "status": "completed",
            "message": "",
            "captured_vars": {
                name: scenario_vars[name]
                for name in phase.local_hook_capture_json
            },
        }

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

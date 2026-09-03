from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from datetime import UTC
from pathlib import Path

from agent_proving_ground._json import as_object, children
from agent_proving_ground.api_adapters.base import ApiAdapter
from agent_proving_ground.api_adapters.local_devrig import (
    LocalDevrigAdapter,
)
from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.api_adapters.remote import RemoteApiAdapter
from agent_proving_ground.artifacts import ArtifactStore
from agent_proving_ground.assertions.registry import AssertionRegistry
from agent_proving_ground.config import (
    DEFAULT_RUNS_ROOT,
    InconclusiveRun,
)
from agent_proving_ground.models import ScenarioResult
from agent_proving_ground.runner import (
    AgentDriverFactory,
    ScenarioRunner,
)
from agent_proving_ground.scenarios.loader import (
    list_builtin_scenarios,
    load_scenario,
)
from agent_proving_ground.timeline import Timeline

_API_ADAPTER_CHOICES = ["mock", "remote", "local-devrig"]
_DRIVER_CHOICES = [
    "scripted",
    "local-process",
    "opencode",
    "codex",
    "claude-code",
    "hermes",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logion-agent-proving-ground",
        description="Multi-agent product proving ground for Logion.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="list builtin scenarios")
    list_cmd.set_defaults(func=_cmd_list)

    validate_cmd = sub.add_parser("validate", help="validate a scenario file")
    validate_cmd.add_argument("scenario", help="scenario file or builtin:NAME")
    validate_cmd.set_defaults(func=_cmd_validate)

    run_cmd = sub.add_parser("run", help="run a scenario")
    run_cmd.add_argument("scenario", help="scenario file or builtin:NAME")
    run_cmd.add_argument(
        "--api-adapter",
        default="mock",
        choices=_API_ADAPTER_CHOICES,
    )
    run_cmd.add_argument(
        "--api-base-url",
        default=None,
        help="override the remote adapter base URL",
    )
    run_cmd.add_argument(
        "--devrig-root",
        default=None,
        help="path to the public logion repo root for local-devrig",
    )
    run_cmd.add_argument(
        "--agent-driver",
        default=None,
        choices=_DRIVER_CHOICES,
    )
    run_cmd.add_argument("--out", help="artifact directory")
    run_cmd.set_defaults(func=_cmd_run)

    report_cmd = sub.add_parser("report", help="print a run report")
    report_cmd.add_argument("run_dir", help="run artifact directory")
    report_cmd.set_defaults(func=_cmd_report)

    doctor_cmd = sub.add_parser("doctor", help="check local readiness")
    doctor_cmd.set_defaults(func=_cmd_doctor)

    return parser


async def _dispatch(args: argparse.Namespace) -> int:
    return await args.func(args)


async def _cmd_list(_args: argparse.Namespace) -> int:
    # Print the kind alongside the name. A rig-driven scenario is a valid
    # integration test and no evidence at all about agent behaviour, and a
    # bare list of names is what lets the second get counted as the first.
    for name in list_builtin_scenarios():
        try:
            spec = load_scenario(f"builtin:{name}")
        except Exception:
            print(f"builtin:{name}\t(unloadable)")
            continue
        agent_phases = len(spec.agent_phase_ids)
        print(
            f"builtin:{name}\t{spec.kind}\t"
            f"{agent_phases}/{len(spec.phases)} agent phases"
        )
    return 0


async def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        spec = load_scenario(args.scenario)
    except Exception as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"scenario is valid (kind: {spec.kind}, "
        f"{len(spec.agent_phase_ids)}/{len(spec.phases)} agent phases)"
    )
    return 0


async def _cmd_run(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    run_id = _make_run_id(scenario.name)
    artifact_root = Path(args.out) if args.out else DEFAULT_RUNS_ROOT / run_id
    artifacts = ArtifactStore(artifact_root)
    artifacts.write_text("scenario.yaml", _scenario_source(args.scenario))

    try:
        api = _build_api_adapter(args)
    except InconclusiveRun as exc:
        print(f"run setup failed: {exc}", file=sys.stderr)
        return 2
    drivers = _build_driver_factory(scenario.driver_config, args.agent_driver)
    timeline = Timeline(artifacts.root / "timeline.jsonl")
    runner = ScenarioRunner(
        scenario=scenario,
        api=api,
        driver_factory=drivers,
        artifacts=artifacts,
        assertions=AssertionRegistry(),
        timeline=timeline,
        run_id=run_id,
    )
    result = await runner.run()
    artifacts.write_json("run.json", result.model_dump(mode="json"))
    _print_report(result)
    return 0 if result.status == "passed" else 1


async def _cmd_report(args: argparse.Namespace) -> int:
    import json

    run_dir = Path(args.run_dir)
    report_json = run_dir / "report.json"
    if not report_json.exists():
        print(f"no report.json in {run_dir}", file=sys.stderr)
        return 2
    data = as_object(
        json.loads(report_json.read_text(encoding="utf-8")),
        where="report",
    )
    print(f"run_id: {data['run_id']}")
    print(f"scenario: {data['scenario']}")
    print(f"status: {data['status']}")
    print(f"api_adapter: {data['api_adapter']}")
    for phase in children(data, "phase_results"):
        print(f"phase {phase['phase_id']}: {phase['status']}")
    for assertion in children(data, "assertion_results"):
        print(f"assertion {assertion['type']}: {assertion['status']}")
    failure = data.get("failure_message")
    if failure:
        print(f"failure: {failure}")
    return 0


async def _cmd_doctor(_args: argparse.Namespace) -> int:
    print("doctor: mock/scripted path available")
    executables = {
        "local-process": None,
        "opencode": "opencode",
        "codex": "codex",
        "claude-code": "claude",
        "hermes": "hermes",
    }
    for driver, executable in executables.items():
        if executable is None:
            print(f"doctor: {driver} requires a scenario agent command")
            continue
        path = shutil.which(executable)
        status = f"available at {path}" if path else "not found"
        print(f"doctor: {driver} ({executable}) {status}")
    return 0


def _make_run_id(scenario_name: str) -> str:
    from datetime import datetime

    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return f"{ts.replace(':', '').replace('-', '')[:15]}-{scenario_name}"


def _scenario_source(source: str) -> str:
    if source.startswith("builtin:"):
        from agent_proving_ground.config import BUILTIN_SCENARIOS_ROOT

        return (
            BUILTIN_SCENARIOS_ROOT / f"{source[len('builtin:') :]}.yaml"
        ).read_text(encoding="utf-8")
    return Path(source).read_text(encoding="utf-8")


def _build_api_adapter(args: argparse.Namespace) -> ApiAdapter:
    name = args.api_adapter
    if name == "mock":
        return MockApiAdapter()
    if name == "remote":
        return RemoteApiAdapter(base_url=args.api_base_url)
    if name == "local-devrig":
        return LocalDevrigAdapter(
            devrig_root=args.devrig_root,
        )
    raise ValueError(f"unsupported api adapter: {name}")


def _build_driver_factory(
    driver_config: dict, override: str | None
) -> AgentDriverFactory:
    return AgentDriverFactory(
        driver_config,
        default_driver=override,
    )


def _print_report(result: ScenarioResult) -> None:
    print(f"run_id: {result.run_id}")
    print(f"scenario: {result.scenario}")
    print(f"status: {result.status}")
    print(f"api_adapter: {result.api_adapter}")
    print(f"artifact_root: {result.artifact_root}")
    for phase in result.phase_results:
        print(f"phase {phase['phase_id']}: {phase['status']}")
    for assertion in result.assertion_results:
        print(f"assertion {assertion.type}: {assertion.status}")
    if result.failure_message:
        print(f"failure: {result.failure_message}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_dispatch(args))

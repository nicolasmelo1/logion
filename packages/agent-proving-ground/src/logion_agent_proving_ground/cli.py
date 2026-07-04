from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC
from pathlib import Path

from logion_agent_proving_ground.api_adapters.mock import MockApiAdapter
from logion_agent_proving_ground.artifacts import ArtifactStore
from logion_agent_proving_ground.assertions.registry import AssertionRegistry
from logion_agent_proving_ground.config import DEFAULT_RUNS_ROOT
from logion_agent_proving_ground.drivers.scripted import ScriptedDriver
from logion_agent_proving_ground.models import ScenarioResult
from logion_agent_proving_ground.runner import (
    AgentDriverFactory,
    ScenarioRunner,
)
from logion_agent_proving_ground.scenarios.loader import (
    list_builtin_scenarios,
    load_scenario,
)
from logion_agent_proving_ground.timeline import Timeline


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
    run_cmd.add_argument("--api-adapter", default="mock", choices=["mock"])
    run_cmd.add_argument(
        "--agent-driver", default="scripted", choices=["scripted"]
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
    for name in list_builtin_scenarios():
        print(f"builtin:{name}")
    return 0


async def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        load_scenario(args.scenario)
    except Exception as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 2
    print("scenario is valid")
    return 0


async def _cmd_run(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    run_id = _make_run_id(scenario.name)
    artifact_root = Path(args.out) if args.out else DEFAULT_RUNS_ROOT / run_id
    artifacts = ArtifactStore(artifact_root)
    artifacts.write_text("scenario.yaml", _scenario_source(args.scenario))

    api = _build_api_adapter(args.api_adapter)
    drivers = _build_driver_factory(args.agent_driver)
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
    data = json.loads(report_json.read_text(encoding="utf-8"))
    print(f"run_id: {data['run_id']}")
    print(f"scenario: {data['scenario']}")
    print(f"status: {data['status']}")
    print(f"api_adapter: {data['api_adapter']}")
    for phase in data.get("phase_results", []):
        print(f"phase {phase['phase_id']}: {phase['status']}")
    for assertion in data.get("assertion_results", []):
        print(f"assertion {assertion['type']}: {assertion['status']}")
    failure = data.get("failure_message")
    if failure:
        print(f"failure: {failure}")
    return 0


async def _cmd_doctor(_args: argparse.Namespace) -> int:
    print("doctor: mock/scripted path available")
    print("doctor: real drivers and remote adapters are not implemented yet")
    return 0


def _make_run_id(scenario_name: str) -> str:
    from datetime import datetime

    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return f"{ts.replace(':', '').replace('-', '')[:15]}-{scenario_name}"


def _scenario_source(source: str) -> str:
    if source.startswith("builtin:"):
        from logion_agent_proving_ground.config import BUILTIN_SCENARIOS_ROOT

        return (
            BUILTIN_SCENARIOS_ROOT / f"{source[len('builtin:') :]}.yaml"
        ).read_text()
    return Path(source).read_text(encoding="utf-8")


def _build_api_adapter(name: str) -> MockApiAdapter:
    if name != "mock":
        raise ValueError(f"unsupported api adapter: {name}")
    return MockApiAdapter()


def _build_driver_factory(name: str) -> AgentDriverFactory:
    if name != "scripted":
        raise ValueError(f"unsupported agent driver: {name}")
    return AgentDriverFactory({"scripted": ScriptedDriver})


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

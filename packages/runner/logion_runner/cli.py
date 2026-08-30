"""``logion-node`` — operator CLI for the reference runner node.

Subcommands: enroll, doctor, run, jobs, rotate-key. Every command
prints a JSON object (machine-readable by default, pretty without
``--compact``), so the operator and the proving-ground capture hook
consume the same output.
"""

from __future__ import annotations

import argparse
import json
import sys

from logion_runner._json import JsonObject


def _print(payload: JsonObject, *, indent: int | None = 2) -> None:
    sys.stdout.write(json.dumps(payload, indent=indent, sort_keys=True) + "\n")


def _fail(message: str, **fields: object) -> int:
    payload = {"ok": False, "failure": message, **fields}
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 1


def cmd_enroll(args: argparse.Namespace) -> int:
    from logion_runner.runner import RunnerNode

    node = RunnerNode.from_env()
    try:
        result = node.enroll(args.name, list(args.capability or []))
    except Exception as exc:
        return _fail(f"enroll failed: {exc}")
    _print({"ok": True, "value": result})
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:  # noqa: ARG001
    from logion_runner.runner import RunnerNode

    node = RunnerNode.from_env()
    doctor_checks = node.doctor()
    checks: list[JsonObject] = [
        {"name": c.name, "ok": c.ok, "detail": c.detail} for c in doctor_checks
    ]
    payload: JsonObject = {
        "ok": all(check.ok for check in doctor_checks),
        "checks": checks,
    }
    _print(payload)
    return 0 if payload["ok"] else 1


def cmd_run(args: argparse.Namespace) -> int:
    from logion_runner.runner import RunnerNode, RunnerNotEnrolled

    node = RunnerNode.from_env()
    try:
        result = node.run(
            once=args.once,
            poll_seconds=args.poll_seconds,
            capabilities=[],
            stop=(lambda: False),
        )
    except RunnerNotEnrolled as exc:
        return _fail(f"not enrolled: {exc}")
    except Exception as exc:
        return _fail(f"run failed: {exc}")
    _print({"ok": True, "value": result})
    return 0


def cmd_jobs(args: argparse.Namespace) -> int:
    from logion_runner.runner import RunnerNode

    node = RunnerNode.from_env()
    entries = node.jobs(limit=args.limit)
    _print({"ok": True, "value": {"jobs": entries, "count": len(entries)}})
    return 0


def cmd_rotate_key(args: argparse.Namespace) -> int:
    from logion_runner.runner import RunnerNode, RunnerNotEnrolled

    node = RunnerNode.from_env()
    try:
        result = node.rotate_key(list(args.capability or []))
    except RunnerNotEnrolled as exc:
        return _fail(f"not enrolled: {exc}")
    except Exception as exc:
        return _fail(f"rotate-key failed: {exc}")
    _print({"ok": True, "value": result})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logion-node",
        description=(
            "Reference isolated runner node for the Logion job system."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    enroll = subparsers.add_parser(
        "enroll", help="Enroll this runner with the coordinator"
    )
    enroll.add_argument("--name", default="", help="Operator-facing name")
    enroll.add_argument(
        "--capability",
        action="append",
        default=[],
        help="Repeatable: declare one capability",
    )
    enroll.add_argument(
        "--base-url",
        default=None,
        help="Coordinator base URL (overrides the environment)",
    )
    enroll.set_defaults(handler=cmd_enroll)

    doctor = subparsers.add_parser(
        "doctor", help="Check state dir, credentials, API, and docker"
    )
    doctor.set_defaults(handler=cmd_doctor)

    run = subparsers.add_parser("run", help="Lease and execute jobs")
    run.add_argument(
        "--once",
        dest="once",
        action="store_true",
        default=True,
        help="Run exactly one lease iteration (default)",
    )
    run.add_argument(
        "--poll-seconds",
        type=int,
        default=5,
        help="Idle sleep between leases when looping",
    )
    run.set_defaults(handler=cmd_run)

    jobs = subparsers.add_parser("jobs", help="Show local run history")
    jobs.add_argument("--limit", type=int, default=20)
    jobs.set_defaults(handler=cmd_jobs)

    rotate = subparsers.add_parser(
        "rotate-key", help="Rotate this runner's key"
    )
    rotate.add_argument(
        "--capability",
        action="append",
        default=[],
        help="Repeatable: declare one capability",
    )
    rotate.set_defaults(handler=cmd_rotate_key)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # --base-url on enroll/doctor overrides the environment for this
    # invocation without persisting anything.
    base_override = getattr(args, "base_url", None)
    if base_override:
        import os

        os.environ["LOGION_NODE_BASE_URL"] = base_override
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

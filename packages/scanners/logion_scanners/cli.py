"""CLI entry point for logion-scanners."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from logion_scanners.adapters.agent import AgentScanner
from logion_scanners.adapters.base import BaseScanner
from logion_scanners.adapters.osv import OsvScanner
from logion_scanners.adapters.trivy import TrivyScanner
from logion_scanners.models import (
    SCANNER_OSV,
    SCANNER_TRIVY,
    ScanPolicy,
    ScanReport,
)
from logion_scanners.policy import load_policy
from logion_scanners.runner import run_scan

_SCANNER_MAP = {
    "agent": AgentScanner,
    "trivy": TrivyScanner,
    "osv": OsvScanner,
}

# CLI scanner name -> model layer constant used in required_scanners.
_SCANNER_LAYER = {
    "agent": "agent_scanner",
    "trivy": "trivy",
    "osv": "osv_scanner",
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="logion-scanners",
        description="Scan a course bundle against a publication policy.",
    )
    sub = parser.add_subparsers(dest="command")

    scan_parser = sub.add_parser("scan", help="Scan a course bundle directory")
    scan_parser.add_argument(
        "path",
        type=Path,
        help="Path to the course bundle directory",
    )
    scan_parser.add_argument(
        "--policy",
        default="publication-v1",
        help="Policy ID to use (default: publication-v1)",
    )
    scan_parser.add_argument(
        "--format",
        choices=["human", "json"],
        default="human",
        help="Output format (default: human)",
    )
    scan_parser.add_argument(
        "--scanner",
        action="append",
        choices=["agent", "trivy", "osv"],
        help="Scanner(s) to run (can be repeated; default: all)",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(2)

    if args.command == "scan":
        _cmd_scan(args)


def _build_adapters(
    scanner_names: list[str],
    policy: ScanPolicy,
) -> list[BaseScanner]:
    """Build scanner adapter instances from names and policy."""
    adapters: list[BaseScanner] = []
    for name in scanner_names:
        if name == "agent":
            adapters.append(
                AgentScanner(
                    enabled_checks=list(policy.enabled_agent_checks),
                    max_file_count=policy.max_file_count,
                    max_file_size_mb=policy.max_file_size_mb,
                )
            )
        elif name == "trivy":
            adapters.append(
                TrivyScanner(
                    docker_image="aquasec/trivy:latest",
                    timeout_seconds=policy.scanner_timeout_seconds,
                )
            )
        elif name == "osv":
            adapters.append(
                OsvScanner(
                    docker_image="ghcr.io/google/osv-scanner:latest",
                    timeout_seconds=policy.scanner_timeout_seconds,
                )
            )
    return adapters


def _check_docker_unavailable(
    scanner_names: list[str],
    report: ScanReport,
) -> None:
    """Exit with code 2 if Docker-required scanners can't run."""
    docker_layers = {"trivy": SCANNER_TRIVY, "osv": SCANNER_OSV}
    for name, layer in docker_layers.items():
        if name not in scanner_names:
            continue
        for result in report.results:
            if (
                result.layer == layer
                and result.error
                and "Docker is not available" in result.error
            ):
                print(  # noqa: T201
                    f"Error: Docker is not available — "
                    f"{name} scanner requires Docker. "
                    f"Install Docker or use --scanner agent.",
                    file=sys.stderr,
                )
                sys.exit(2)


def _cmd_scan(args: argparse.Namespace) -> None:
    bundle: Path = args.path.resolve()
    if not bundle.is_dir():
        print(  # noqa: T201
            f"Error: {bundle} is not a directory",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        policy = load_policy(args.policy)
    except ValueError as exc:
        print(  # noqa: T201
            f"Error: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    scanner_names: list[str] = (
        args.scanner if args.scanner else ["agent", "trivy", "osv"]
    )
    # When the user explicitly selects scanners via --scanner, scope the
    # policy so only those scanners are considered required.  This avoids
    # blocking on missing scanners that the user intentionally skipped.
    if args.scanner:
        requested_layers = tuple(_SCANNER_LAYER[n] for n in scanner_names)
        policy = dataclasses.replace(
            policy,
            required_scanners=requested_layers,
        )
    adapters = _build_adapters(scanner_names, policy)
    report = run_scan(bundle=bundle, policy=policy, adapters=adapters)
    _check_docker_unavailable(scanner_names, report)

    if args.format == "json":
        print(  # noqa: T201
            json.dumps(report.to_dict(), indent=2)
        )
    else:
        _print_human(report, policy)

    if report.execution_error:
        sys.exit(2)
    elif report.decision.allowed:
        sys.exit(0)
    else:
        sys.exit(1)


def _print_human(report: ScanReport, policy: ScanPolicy) -> None:
    """Print human-readable scan report."""
    print(  # noqa: T201
        f"Policy: {report.policy_id} v{report.policy_version}"
    )
    print(f"Policy hash: {report.policy_hash}")  # noqa: T201
    print(f"Bundle hash: {report.bundle_hash}")  # noqa: T201
    print()  # noqa: T201

    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{result.layer}] {status}")  # noqa: T201
        if result.error:
            print(f"  Error: {result.error}")  # noqa: T201
        blocking_sevs = set(policy.blocking_severities.get(result.layer, ()))
        for finding in result.findings:
            marker = "BLOCKS" if finding.severity in blocking_sevs else "info"
            loc = ""
            if finding.file_path:
                loc = f" {finding.file_path}"
                if finding.line_number:
                    loc += f":{finding.line_number}"
            print(  # noqa: T201
                f"  [{marker}] {finding.rule_id}: {finding.description}{loc}"
            )

    print()  # noqa: T201
    if report.decision.allowed:
        print("Decision: ALLOWED")  # noqa: T201
    else:
        print("Decision: BLOCKED")  # noqa: T201
        for reason in report.decision.reasons:
            print(f"  - {reason}")  # noqa: T201

#!/usr/bin/env python3
"""CLI: crawl, resolve, push, run, doctor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import IndexerConfig, SeedFile
from .dedup import dedup, dry_run_plan
from .models import DiscoveredSkill
from .pusher import Pusher, RunStats
from .transport import Transport


def _build_transport(config: IndexerConfig) -> Transport:
    return Transport(
        user_agent=config.user_agent,
        github_token=config.github_token or None,
        api_key=config.api_key or None,
    )


def _load_seed(config: IndexerConfig) -> SeedFile:
    path = config.seed_file or str(SeedFile.default_path())
    return SeedFile.load(path)


def _get_adapter(
    adapter_name: str,
    transport: Transport,
):
    """Instantiate an adapter by name."""
    if adapter_name == "github_direct":
        from .adapters.github_direct import GithubDirectAdapter

        return GithubDirectAdapter(transport=transport)
    if adapter_name == "skills_sh":
        from .adapters.skills_sh import SkillsShAdapter

        return SkillsShAdapter(transport=transport)
    if adapter_name == "clawhub":
        from .adapters.clawhub import ClawhubAdapter

        return ClawhubAdapter(transport=transport)
    if adapter_name == "lobehub":
        from .adapters.lobehub import LobehubAdapter

        return LobehubAdapter(transport=transport)
    if adapter_name == "browse_sh":
        from .adapters.browse_sh import BrowseShAdapter

        return BrowseShAdapter(transport=transport)
    if adapter_name == "hermes_docs":
        from .adapters.hermes_docs import HermesDocsAdapter

        return HermesDocsAdapter(transport=transport)
    if adapter_name == "skills_lock":
        from .adapters.skills_lock import SkillsLockAdapter

        return SkillsLockAdapter(transport=transport)
    raise ValueError(f"unknown adapter: {adapter_name}")


def _discover_all(
    config: IndexerConfig,
    transport: Transport,
) -> list[DiscoveredSkill]:
    """Run all adapters from the seed file and collect discoveries."""
    seed = _load_seed(config)
    all_discoveries: list[DiscoveredSkill] = []

    for source in seed.sources:
        if config.only and source.adapter != config.only:
            continue
        adapter = _get_adapter(source.adapter, transport)
        kwargs: dict = {}
        if source.mode:
            kwargs["mode"] = source.mode
        if source.subpath:
            kwargs["subpath"] = source.subpath
        try:
            for skill in adapter.discover(
                source.target,
                limit=config.limit,
                **kwargs,
            ):
                all_discoveries.append(skill)
        except Exception as e:
            print(f"adapter {source.adapter} error: {e}", file=sys.stderr)

    return all_discoveries


def cmd_crawl(config: IndexerConfig, args: argparse.Namespace) -> int:
    """Crawl hubs, produce a plan (no push)."""
    transport = _build_transport(config)
    discoveries = _discover_all(config, transport)
    plan = dry_run_plan(discoveries, transport, config.api_base_url)
    print(f"discovered: {len(discoveries)}")
    print(f"create: {len(plan.create)}")
    print(f"update: {len(plan.update)}")
    print(f"skip: {len(plan.skip)}")
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2))
    return 0


def cmd_resolve(config: IndexerConfig, args: argparse.Namespace) -> int:  # noqa: ARG001
    """Resolve hub pages to GitHub identities (debug command)."""
    transport = _build_transport(config)
    discoveries = _discover_all(config, transport)
    print(f"resolved: {len(discoveries)} skills")
    for d in discoveries[:20]:
        print(f"  {d.canonical} — {d.title or '(no title)'}")
    return 0


def cmd_push(config: IndexerConfig, args: argparse.Namespace) -> int:
    """Push a pre-built plan to the API."""
    transport = _build_transport(config)
    plan_path = Path(args.plan)
    with open(plan_path) as fh:
        plan_data = json.load(fh)
    print(f"push: loaded plan from {plan_path}")
    print(f"  create: {len(plan_data.get('create', []))}")
    print(f"  update: {len(plan_data.get('update', []))}")
    print(f"  skip: {len(plan_data.get('skip', []))}")
    pusher = Pusher(transport, config.api_base_url)
    run_id = pusher.open_run()
    print(f"  run_id: {run_id}")
    stats = RunStats()
    pusher.close_run(stats)
    return 0


def cmd_run(config: IndexerConfig, args: argparse.Namespace) -> int:  # noqa: ARG001
    """Full pipeline: crawl → resolve → dedup → push → stats."""
    transport = _build_transport(config)
    discoveries = _discover_all(config, transport)
    stats = RunStats(discovered=len(discoveries))

    if config.dry_run:
        plan = dry_run_plan(discoveries, transport, config.api_base_url)
        stats.created = len(plan.create)
        stats.updated = len(plan.update)
        stats.skipped = len(plan.skip)
        _print_stats(stats)
        return 0

    plan = dedup(discoveries, transport, config.api_base_url)
    stats.deduped = plan.total
    stats.created = len(plan.create)
    stats.updated = len(plan.update)
    stats.skipped = len(plan.skip)

    pusher = Pusher(transport, config.api_base_url)
    run_id = pusher.open_run()
    if plan.create:
        result = pusher.push_batch(plan.create, run_id=run_id)
        stats.created = result.created
        stats.errors += result.errors
        if result.errors:
            stats.partial = True
    if plan.update:
        result = pusher.push_batch(plan.update, run_id=run_id)
        stats.updated = result.updated
        stats.errors += result.errors
        if result.errors:
            stats.partial = True

    pusher.close_run(stats)
    _print_stats(stats)
    return 1 if stats.partial else 0


def cmd_doctor(config: IndexerConfig, args: argparse.Namespace) -> int:  # noqa: ARG001
    """Check credentials, robots.txt, and API reachability."""
    redacted = config.redact()
    print("configuration:")
    for key, val in redacted.items():
        print(f"  {key}: {val}")

    transport = _build_transport(config)
    # Check API reachability.
    try:
        resp = transport.get(f"{config.api_base_url}/health")
        print(f"  api: HTTP {resp.status}")
    except Exception as e:
        print(f"  api: unreachable ({e})")
        return 1

    print("doctor: ok")
    return 0


def _print_stats(stats: RunStats) -> None:
    print(
        f"run: discovered={stats.discovered} "
        f"resolved={stats.resolved} "
        f"deduped={stats.deduped} "
        f"created={stats.created} "
        f"updated={stats.updated} "
        f"skipped={stats.skipped} "
        f"errors={stats.errors} "
        f"partial={'yes' if stats.partial else 'no'}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logion-indexer",
        description="External skillhub indexer for Logion.",
    )
    parser.add_argument(
        "--seed-file",
        default=None,
        help="seed file path (default: bundled seeds/sources.yaml)",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="run only this adapter",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="max items per adapter",
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=1.0,
        help="rate limit (requests per second, per host)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="plan only, no push",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="output as JSON",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("crawl", help="crawl hubs, print plan")
    subparsers.add_parser("resolve", help="resolve hub pages to GitHub")
    subparsers.add_parser("run", help="full pipeline: crawl → push")
    subparsers.add_parser("doctor", help="check creds, robots, API")

    push_parser = subparsers.add_parser("push", help="push a plan file")
    push_parser.add_argument("--plan", required=True, help="plan JSON file")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = IndexerConfig.from_env(
        seed_file=args.seed_file,
        only=args.only,
        limit=args.limit,
        rps=args.rps,
        dry_run=args.dry_run,
    )

    if args.command == "crawl":
        sys.exit(cmd_crawl(config, args))
    elif args.command == "resolve":
        sys.exit(cmd_resolve(config, args))
    elif args.command == "push":
        sys.exit(cmd_push(config, args))
    elif args.command == "run":
        sys.exit(cmd_run(config, args))
    elif args.command == "doctor":
        sys.exit(cmd_doctor(config, args))
    else:
        parser.print_help()
        sys.exit(1)

#!/usr/bin/env python3
"""CLI: crawl, resolve, push, run, doctor."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .config import IndexerConfig, SeedFile
from .crawl import Crawler
from .mirror import BundleArtifact
from .models import DiscoveredSkill
from .pipeline import build_indexing_plan
from .pusher import Pusher, PushResult, RunStats
from .rate_limit import RateLimiter
from .transport import Transport

MAX_PUSH_ERROR_DETAILS = 20


@dataclass(frozen=True)
class AdapterFailure:
    """Failure returned by one discovery adapter."""

    adapter: str
    target: str
    error: str


@dataclass
class DiscoveryResult:
    """Discoveries and adapter failures from one crawl."""

    discoveries: list[DiscoveredSkill] = field(default_factory=list)
    failures: list[AdapterFailure] = field(default_factory=list)


def _build_transport(config: IndexerConfig) -> Transport:
    transport = Transport(
        user_agent=config.user_agent,
        github_token=config.github_token or None,
        api_key=config.api_key or None,
        cache_dir=config.resolved_cache_dir,
    )
    transport.set_api_base_url(config.api_base_url)
    return transport


def _load_seed(config: IndexerConfig) -> SeedFile:
    path = config.seed_file or str(SeedFile.default_path())
    return SeedFile.load(path)


def _get_adapter(
    adapter_name: str,
    transport: Transport,
    rate_limiter: RateLimiter | None = None,
):
    """Instantiate an adapter by name."""
    if adapter_name == "github_direct":
        from .adapters.github_direct import GithubDirectAdapter

        return GithubDirectAdapter(transport=transport)
    if adapter_name == "skills_sh":
        from .adapters.skills_sh import SkillsShAdapter

        return SkillsShAdapter(transport=transport, rate_limiter=rate_limiter)
    if adapter_name == "clawhub":
        from .adapters.clawhub import ClawhubAdapter

        return ClawhubAdapter(transport=transport, rate_limiter=rate_limiter)
    if adapter_name == "browse_sh":
        from .adapters.browse_sh import BrowseShAdapter

        return BrowseShAdapter(transport=transport, rate_limiter=rate_limiter)
    if adapter_name == "skillsmp":
        from .adapters.skillsmp import SkillsMpAdapter

        return SkillsMpAdapter(transport=transport, rate_limiter=rate_limiter)
    if adapter_name == "smithery":
        from .adapters.smithery import SmitheryAdapter

        return SmitheryAdapter(transport=transport, rate_limiter=rate_limiter)
    if adapter_name == "hermes_docs":
        from .adapters.hermes_docs import HermesDocsAdapter

        return HermesDocsAdapter(
            transport=transport, rate_limiter=rate_limiter
        )
    if adapter_name == "skills_lock":
        from .adapters.skills_lock import SkillsLockAdapter

        return SkillsLockAdapter(
            transport=transport,
            rate_limiter=rate_limiter,
        )
    raise ValueError(f"unknown adapter: {adapter_name}")


def _discover_all(
    config: IndexerConfig,
    transport: Transport,
) -> DiscoveryResult:
    """Run all adapters from the seed file and collect discoveries."""
    seed = _load_seed(config)
    result = DiscoveryResult()
    rate_limiter = RateLimiter(default_rps=config.rps)

    for source in seed.sources:
        if config.only and source.adapter != config.only:
            continue
        try:
            adapter = _get_adapter(source.adapter, transport, rate_limiter)
            kwargs: dict = {}
            if source.mode:
                kwargs["mode"] = source.mode
            if source.subpath:
                kwargs["subpath"] = source.subpath
            for skill in adapter.discover(
                source.target,
                limit=config.limit,
                **kwargs,
            ):
                result.discoveries.append(skill)
        except Exception as e:
            result.failures.append(
                AdapterFailure(source.adapter, source.target, str(e))
            )
            print(f"adapter {source.adapter} error: {e}", file=sys.stderr)

    return result


def cmd_crawl(config: IndexerConfig, args: argparse.Namespace) -> int:
    """Crawl hubs, produce a plan (no push).

    With ``--out plan.json`` the full plan (create/update items serialized
    verbatim) is written for a later ``push --plan``; ``--json`` prints the
    same payload to stdout.
    """
    transport = _build_transport(config)
    discovery = _discover_all(config, transport)
    plan, _ = build_indexing_plan(
        discovery.discoveries,
        transport,
        config.api_base_url,
        mirror=False,
    )
    plan.partial = plan.partial or bool(discovery.failures)
    diagnostics = sys.stderr if args.json else sys.stdout
    print(f"discovered: {len(discovery.discoveries)}", file=diagnostics)
    print(f"create: {len(plan.create)}", file=diagnostics)
    print(f"update: {len(plan.update)}", file=diagnostics)
    print(f"skip: {len(plan.skip)}", file=diagnostics)
    print(f"partial: {'yes' if plan.partial else 'no'}", file=diagnostics)
    plan_dict = plan.to_dict()
    if args.out:
        Path(args.out).write_text(json.dumps(plan_dict, indent=2))
        print(f"wrote plan: {args.out}", file=diagnostics)
    if args.json:
        print(json.dumps(plan_dict, indent=2))
    return 0


def cmd_resolve(config: IndexerConfig, args: argparse.Namespace) -> int:  # noqa: ARG001
    """Resolve hub pages to GitHub identities (debug command)."""
    transport = _build_transport(config)
    discovery = _discover_all(config, transport)
    print(f"resolved: {len(discovery.discoveries)} skills")
    for d in discovery.discoveries[:20]:
        print(f"  {d.canonical} — {d.title or '(no title)'}")
    return 1 if discovery.failures else 0


def cmd_push(config: IndexerConfig, args: argparse.Namespace) -> int:
    """Push a pre-built plan file to the API, verbatim.

    The plan file carries the full serialized items (the same
    serialization the pusher sends), so items are pushed as-is with no
    degenerate rebuilds.  Bundle bytes are not in the plan file, so
    ``push --plan`` is link/metadata only; the full ``run`` path mirrors
    bundles.
    """
    transport = _build_transport(config)
    plan_path = Path(args.plan)
    with open(plan_path) as fh:
        plan_data = json.load(fh)
    create_items = plan_data.get("create", [])
    update_items = plan_data.get("update", [])
    skip_count = len(plan_data.get("skip", []))
    print(f"push: loaded plan from {plan_path}")
    print(f"  create: {len(create_items)}")
    print(f"  update: {len(update_items)}")
    print(f"  skip: {skip_count}")

    pusher = Pusher(transport, config.api_base_url)
    run_id = pusher.open_run()
    print(f"  run_id: {run_id}")

    stats = RunStats(skipped=skip_count)
    stats.partial = bool(plan_data.get("partial", False))

    if create_items:
        result = pusher.push_serialized(create_items, run_id=run_id)
        stats.created = result.created
        stats.errors += result.errors
        _print_push_errors(result, config)
        if result.errors:
            stats.partial = True

    if update_items:
        result = pusher.push_serialized(update_items, run_id=run_id)
        stats.updated = result.updated
        stats.errors += result.errors
        _print_push_errors(result, config)
        if result.errors:
            stats.partial = True

    pusher.close_run(stats)
    _print_stats(stats)
    return 1 if stats.partial else 0


def cmd_run(config: IndexerConfig, args: argparse.Namespace) -> int:
    """Full pipeline: crawl → enrich → validate → mirror → push → stats."""
    transport = _build_transport(config)
    discovery = _discover_all(config, transport)
    stats = RunStats(discovered=len(discovery.discoveries))

    plan, artifacts = build_indexing_plan(
        discovery.discoveries,
        transport,
        config.api_base_url,
        mirror=not getattr(args, "link_only", False),
    )
    stats.deduped = plan.total
    stats.skipped = len(plan.skip)
    stats.partial = plan.partial or bool(discovery.failures)

    if config.dry_run:
        stats.created = len(plan.create)
        stats.updated = len(plan.update)
        _print_stats(stats)
        return 1 if stats.partial else 0

    pusher = Pusher(transport, config.api_base_url)
    run_id = pusher.open_run()
    if plan.create:
        result = pusher.push_batch(plan.create, run_id=run_id)
        stats.created = result.created
        stats.errors += result.errors
        _print_push_errors(result, config)
        if result.errors:
            stats.partial = True
        _upload_bundles(pusher, result, artifacts)
    if plan.update:
        result = pusher.push_batch(plan.update, run_id=run_id)
        stats.updated = result.updated
        stats.errors += result.errors
        _print_push_errors(result, config)
        if result.errors:
            stats.partial = True
        _upload_bundles(pusher, result, artifacts)

    pusher.close_run(stats)
    _print_stats(stats)
    return 1 if stats.partial else 0


def _upload_bundles(
    pusher: Pusher,
    result: PushResult,
    artifacts: dict[str, BundleArtifact],
) -> None:
    """Upload mirrored bundles for upserted listings via presigned PUT."""
    for canonical, listing_id in result.listing_ids.items():
        artifact = artifacts.get(canonical)
        if artifact is None:
            continue
        pusher.upload_bundle(listing_id, artifact.data, artifact.sha256)


def _print_push_errors(result: PushResult, config: IndexerConfig) -> None:
    """Print bounded, redacted per-item push diagnostics to stderr."""
    secrets = tuple(
        secret for secret in (config.github_token, config.api_key) if secret
    )
    for detail in result.error_details[:MAX_PUSH_ERROR_DETAILS]:
        canonical = _safe_detail(detail.get("canonical"), secrets)
        status = _safe_detail(detail.get("status"), secrets)
        error = _safe_detail(
            detail.get("error") or detail.get("message"), secrets
        )
        body = _safe_detail(detail.get("body"), secrets)
        print(
            "push error: "
            f"canonical={canonical} status={status} error={error} body={body}",
            file=sys.stderr,
        )
    omitted = len(result.error_details) - MAX_PUSH_ERROR_DETAILS
    if omitted > 0:
        print(
            f"push errors: omitted={omitted} additional details",
            file=sys.stderr,
        )


def _safe_detail(value: object, secrets: tuple[str, ...]) -> str:
    """Render one diagnostic field without multiline or credential leakage."""
    if value is None or value == "":
        return "(unknown)"
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, separators=(",", ":"), default=str)
    else:
        rendered = str(value)
    for secret in secrets:
        rendered = rendered.replace(secret, "[redacted]")
    rendered = re.sub(
        r"(?i)\bBearer\s+[^\s,;\"'}]+", "Bearer [redacted]", rendered
    )
    rendered = re.sub(
        r"\b(?:gh[pousr]_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+)\b",
        "[redacted]",
        rendered,
    )
    return rendered.replace("\r", "\\r").replace("\n", "\\n")[:500]


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

    _check_robots(config, transport)

    print("doctor: ok")
    return 0


def _check_robots(config: IndexerConfig, transport: Transport) -> None:
    """Report robots.txt fetchability for each non-GitHub seed hub."""
    try:
        seed = _load_seed(config)
    except (FileNotFoundError, ImportError, TypeError) as e:
        print(f"  robots: seed file unreadable ({e})")
        return
    crawler = Crawler(transport)
    seen: set[str] = set()
    print("  robots:")
    for source in seed.sources:
        if source.adapter == "github_direct":
            continue
        host = urlparse(source.target).hostname or ""
        if not host or host in seen:
            continue
        seen.add(host)
        rule = crawler.fetch_robots_txt(source.target)
        disallowed = len(rule.disallowed_paths)
        print(f"    {host}: reachable (disallow rules: {disallowed})")


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
        "--cache-dir",
        default=None,
        help="on-disk HTTP cache dir (default: ~/.cache/logion-indexer)",
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

    crawl_parser = subparsers.add_parser(
        "crawl", help="crawl hubs, print plan"
    )
    crawl_parser.add_argument(
        "--out",
        default=None,
        help="write the full plan to this JSON file (for push --plan)",
    )
    subparsers.add_parser("resolve", help="resolve hub pages to GitHub")
    run_parser = subparsers.add_parser(
        "run", help="full pipeline: crawl → push"
    )
    run_parser.add_argument(
        "--link-only",
        action="store_true",
        help="skip bundle mirroring and ingest metadata/provenance only",
    )
    subparsers.add_parser("doctor", help="check creds, robots, API")

    push_parser = subparsers.add_parser("push", help="push a plan file")
    push_parser.add_argument("--plan", required=True, help="plan JSON file")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    from_env_kwargs: dict = {
        "seed_file": args.seed_file,
        "only": args.only,
        "limit": args.limit,
        "rps": args.rps,
        "dry_run": args.dry_run,
    }
    if args.cache_dir is not None:
        from_env_kwargs["cache_dir"] = args.cache_dir
    config = IndexerConfig.from_env(**from_env_kwargs)

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

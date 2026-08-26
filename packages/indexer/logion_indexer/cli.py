#!/usr/bin/env python3
"""CLI: crawl, resolve, push, run, doctor."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO
from urllib.parse import urlparse

from .config import IndexerConfig, SeedFile
from .crawl import Crawler
from .dedup import DedupPlan, ResourceDedupPlan
from .import_report import ImportReport, QuarantinedRecord
from .mirror import BundleArtifact
from .models import DiscoveredResource, DiscoveredSkill
from .pipeline import (
    build_indexing_plan,
    build_resource_indexing_plan,
    partition_discoveries,
)
from .progress import RunProgress
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

    discoveries: list[DiscoveredSkill | DiscoveredResource] = field(
        default_factory=list
    )
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
    if adapter_name == "dsh_hub":
        from .adapters.dsh_hub import DshHubAdapter

        return DshHubAdapter(transport=transport)
    if adapter_name == "ai-catalog":
        from .adapters.ai_catalog import AICatalogAdapter

        return AICatalogAdapter(transport=transport)
    if adapter_name == "ard":
        from .adapters.ard import ARDAdapter

        return ARDAdapter(transport=transport)
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
    config = _crawl_config(config, args)
    started = time.monotonic()
    transport = _build_transport(config)
    discovery, quarantine, entries_seen = _run_discovery(
        config, args, transport
    )
    skills, resources = partition_discoveries(discovery.discoveries)
    plan, _ = build_indexing_plan(
        skills,
        transport,
        config.api_base_url,
        mirror=False,
    )
    resource_plan = build_resource_indexing_plan(
        resources, transport, config.api_base_url, digest=False
    )
    plan.partial = plan.partial or bool(discovery.failures)
    plan_dict = _merged_plan_dict(plan, resource_plan)
    diagnostics = sys.stderr if args.json else sys.stdout
    _print_plan_counts(discovery, plan_dict, plan.partial, diagnostics)
    report = _build_import_report(
        config=config,
        args=args,
        plan_dict=plan_dict,
        quarantine=quarantine,
        entries_seen=entries_seen,
        partial=plan.partial,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    for line in report.summary_lines():
        print(line, file=diagnostics)
    if getattr(args, "ingest", False):
        ingested = _ingest_entries(
            config, transport, args, discovery.discoveries
        )
        if ingested is None:
            return 1
        _apply_ingestion(report, ingested)
        print(
            f"ingested: {report.created} created, {report.matched} matched",
            file=diagnostics,
        )
    _write_crawl_outputs(args, plan_dict, report, diagnostics)
    return _crawl_exit_code(args, report)


def _print_plan_counts(
    discovery: DiscoveryResult,
    plan_dict: dict,
    partial: bool,
    diagnostics: TextIO,
) -> None:
    """Print what the plan would do, before what the run actually did."""
    print(f"discovered: {len(discovery.discoveries)}", file=diagnostics)
    print(f"create: {len(plan_dict['create'])}", file=diagnostics)
    print(f"update: {len(plan_dict['update'])}", file=diagnostics)
    print(f"skip: {len(plan_dict['skip'])}", file=diagnostics)
    print(f"partial: {'yes' if partial else 'no'}", file=diagnostics)


def _crawl_exit_code(
    args: argparse.Namespace,
    report: ImportReport,
) -> int:
    """A partial import is a documented non-zero exit.

    A crawl that dropped entries and still exits 0 teaches every caller
    above it that quarantine is normal.
    """
    if not report.quarantined or getattr(args, "allow_quarantine", False):
        return 0
    plural = "y" if report.quarantined == 1 else "ies"
    print(
        f"quarantined {report.quarantined} entr{plural}; "
        f"pass --allow-quarantine to accept a partial import",
        file=sys.stderr,
    )
    return 2


def _write_crawl_outputs(
    args: argparse.Namespace,
    plan_dict: dict,
    report: ImportReport,
    diagnostics: TextIO,
) -> None:
    """Emit the plan and the report where the caller asked for them.

    They are different artifacts: the plan is a resume-able push
    payload, the report is the account of what this run saw and
    refused. Writing one to the other's path loses whichever it
    overwrites.
    """
    if args.out:
        Path(args.out).write_text(json.dumps(plan_dict, indent=2))
        print(f"wrote plan: {args.out}", file=diagnostics)
    if getattr(args, "report", None):
        report.write(args.report)
        print(f"wrote import report: {args.report}", file=diagnostics)
    if args.json:
        print(json.dumps(plan_dict, indent=2))


def _apply_ingestion(report: ImportReport, ingested: dict) -> None:
    """Replace the crawler's intent with the registry's answer.

    What the crawler planned to write and what the registry decided to
    create are different numbers. The report carries the second, because
    that is the one an operator can act on.
    """
    report.created = ingested.get("created", report.created)
    report.matched = ingested.get("matched", report.matched)
    for entry in ingested.get("quarantine", []):
        report.quarantine.append(
            QuarantinedRecord(
                identifier=str(entry.get("identifier", "")),
                error_code=str(entry.get("error_code", "")),
                reason=str(entry.get("reason", "")),
            )
        )


def _ingest_entries(
    config: IndexerConfig,
    transport: Transport,
    args: argparse.Namespace,
    discoveries: list,
) -> dict | None:
    """Record discovered entries as resources with catalog provenance.

    The counters come back from the registry rather than from the plan:
    what the crawler intended to write and what the registry decided to
    create are different numbers, and the import report should carry the
    one that actually happened.
    """
    entries = [
        {
            "identifier": item.canonical_uri.removeprefix("air:"),
            "type": _catalog_media_type(item),
            "title": item.title or "",
            "summary": item.summary or None,
            "tags": list(item.tags),
            "publisher": item.original_author or None,
            "url": _catalog_entry_url(item),
        }
        for item in discoveries
        if isinstance(item, DiscoveredResource)
    ]
    url = f"{config.api_base_url.rstrip('/')}/v1/resources:ingest-catalog"
    transport.set_api_base_url(config.api_base_url)
    resp = transport.post(
        url,
        json_body={
            "source_uri": getattr(args, "entrypoint", "") or "",
            "source_kind": "ai_catalog_entry",
            "entries": entries,
        },
    )
    if resp.status != 200:
        print(
            f"ingest: registry refused the entries (HTTP {resp.status})",
            file=sys.stderr,
        )
        return None
    try:
        payload = resp.json()
    except (ValueError, json.JSONDecodeError):
        print("ingest: registry returned invalid JSON", file=sys.stderr)
        return None
    return payload if isinstance(payload, dict) else None


def _catalog_entry_url(item: DiscoveredResource) -> str | None:
    """Recover the artifact URL the catalog entry declared.

    Kept in channel metadata for the same reason the media type is: it
    is the entry's own statement about itself, and a resource row has
    nowhere else to put it. Without it the registry can only publish a
    URL of its own for an artifact it does not serve.
    """
    for channel in item.channels:
        for key, value in channel.metadata:
            if key == "ai_catalog_url":
                return str(value)
    return None


def _catalog_media_type(item: DiscoveredResource) -> str:
    """Recover the media type the catalog entry declared.

    The adapter keeps it in channel metadata rather than on the resource,
    because a Logion resource type and an AI Catalog media type are not
    the same vocabulary and collapsing them here would lose the entry's
    own word for what it is.
    """
    for channel in item.channels:
        for key, value in channel.metadata:
            if key == "ai_catalog_type":
                return str(value)
    return _RESOURCE_TYPE_TO_MEDIA_TYPE.get(
        item.resource_type, "application/octet-stream"
    )


#: The catalog media type each Logion resource type is published as.
#: Mirrors the registry's own map so a re-crawl of our own catalog
#: recovers the type it started with.
_RESOURCE_TYPE_TO_MEDIA_TYPE: dict[str, str] = {
    "skill": "application/agent-skills+json",
    "agent_skill": "application/agent-skills+json",
    "mcp_server": "application/mcp-server-card+json",
    "catalog": "application/ai-catalog+json",
    "registry": "application/ai-registry+json",
}


def _crawl_config(
    config: IndexerConfig,
    args: argparse.Namespace,
) -> IndexerConfig:
    """Apply --adapter, which is shorthand for --only."""
    if not getattr(args, "adapter", None) or config.only:
        return config
    return IndexerConfig(
        github_token=config.github_token,
        api_key=config.api_key,
        base_url=config.base_url,
        seed_file=config.seed_file,
        cache_dir=config.cache_dir,
        user_agent=config.user_agent,
        rps=config.rps,
        dry_run=config.dry_run,
        limit=config.limit,
        only=args.adapter,
    )


def _run_discovery(
    config: IndexerConfig,
    args: argparse.Namespace,
    transport: Transport,
) -> tuple[DiscoveryResult, list[QuarantinedRecord], int]:
    """Discover from one entrypoint, or from every seeded source.

    Returns what was found, what was refused, and how many entries the
    source offered -- the third is not derivable from the first two,
    because a quarantined entry is neither discovered nor absent.
    """
    if not (getattr(args, "entrypoint", None) and config.only):
        discovery = _discover_all(config, transport)
        return discovery, [], len(discovery.discoveries)

    adapter = _get_adapter(config.only, transport)
    try:
        discovered, quarantine, seen = _discover_entrypoint(
            adapter, args.entrypoint, config.limit
        )
    except Exception as e:
        print(f"adapter {config.only} error: {e}", file=sys.stderr)
        failure = AdapterFailure(config.only, args.entrypoint, str(e))
        return DiscoveryResult(discoveries=[], failures=[failure]), [], 0
    return DiscoveryResult(discoveries=discovered), quarantine, seen


def _discover_entrypoint(
    adapter: object,
    entrypoint: str,
    limit: int | None,
) -> tuple[list[DiscoveredSkill | DiscoveredResource], list, int]:
    """Discover from one URL, keeping what the adapter refused.

    ``discover`` yields only what survived, which is exactly the half a
    quarantine report cannot be built from. Adapters that expose
    ``crawl`` return both halves, so prefer it and fall back for the
    ones that do not.
    """
    crawl = getattr(adapter, "crawl", None)
    if crawl is None:
        items = list(
            adapter.discover(entrypoint, limit=limit)  # type: ignore[attr-defined]
        )
        return items, [], len(items)
    result = crawl(entrypoint, limit=limit)
    quarantine = [
        QuarantinedRecord(
            identifier=rejection.identifier,
            error_code=rejection.error_code,
            reason=rejection.reason,
        )
        for rejection in result.rejected
    ]
    return list(result.resources), quarantine, result.seen


def _build_import_report(
    *,
    config: IndexerConfig,
    args: argparse.Namespace,
    plan_dict: dict,
    quarantine: list,
    entries_seen: int,
    partial: bool,
    duration_ms: int,
) -> ImportReport:
    """Turn a finished crawl into the record an operator can audit."""
    created = plan_dict["create"]
    matched = plan_dict["update"] + plan_dict["skip"]
    # Counted, not assumed: an AI Catalog entry is a selection
    # descriptor and must never mint a ResourceVersion, and the only
    # honest way to report that is to look at what the plan carries.
    new_versions = sum(
        1 for item in created + plan_dict["update"] if item.get("bundle")
    )
    return ImportReport(
        source=getattr(args, "entrypoint", None) or str(config.seed_file),
        adapter=config.only or "all",
        seen=entries_seen if entries_seen else len(created) + len(matched),
        created=len(created),
        matched=len(matched),
        new_versions=new_versions,
        cursor=None,
        duration_ms=duration_ms,
        partial=partial,
        quarantine=list(quarantine),
    )


def _merged_plan_dict(plan: DedupPlan, resources: ResourceDedupPlan) -> dict:
    """Merge both vocabularies into one push payload.

    Both serialize to the same batch-upsert item shape, so a plan file
    stays a single resume-able payload no matter which adapters ran.
    """
    skill_dict = plan.to_dict()
    resource_dict = resources.to_dict()
    return {
        "create": skill_dict["create"] + resource_dict["create"],
        "update": skill_dict["update"] + resource_dict["update"],
        "skip": skill_dict["skip"] + resource_dict["skip"],
        "partial": skill_dict["partial"] or resource_dict["partial"],
    }


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


def cmd_run(  # noqa: C901 - terminal receipts share one lifecycle.
    config: IndexerConfig, args: argparse.Namespace
) -> int:
    """Full pipeline: crawl → enrich → validate → mirror → push → stats."""
    transport = _build_transport(config)
    stats = RunStats()
    pusher = None
    progress = None
    run_id = None
    if not config.dry_run:
        pusher = Pusher(transport, config.api_base_url)
        run_id = pusher.open_run()
        progress = RunProgress(transport, config.api_base_url, run_id, stats)
        progress.checkpoint("discovering")
    try:
        discovery = _discover_all(config, transport)
        stats.discovered = len(discovery.discoveries)
        if progress:
            progress.checkpoint("enriching")

        skills, resources = partition_discoveries(discovery.discoveries)
        plan, _artifacts = build_indexing_plan(
            skills,
            transport,
            config.api_base_url,
            mirror=not getattr(args, "link_only", False),
        )
        resource_plan = build_resource_indexing_plan(
            resources,
            transport,
            config.api_base_url,
            digest=not getattr(args, "link_only", False),
        )
        stats.deduped = plan.total + resource_plan.total
        stats.skipped = len(plan.skip) + len(resource_plan.skip)
        stats.partial = plan.partial or bool(discovery.failures)
        if progress:
            progress.checkpoint("planning")

        if config.dry_run:
            stats.created = len(plan.create) + len(resource_plan.create)
            stats.updated = len(plan.update) + len(resource_plan.update)
            _print_stats(stats)
            return 1 if stats.partial else 0

        assert pusher is not None
        if progress:
            progress.checkpoint("pushing")
        if plan.create:
            result = pusher.push_batch(plan.create, run_id=run_id)
            stats.created = result.created
            stats.errors += result.errors
            _print_push_errors(result, config)
            if result.errors:
                stats.partial = True
            _upload_bundles(pusher, result, _artifacts)
        if plan.update:
            result = pusher.push_batch(plan.update, run_id=run_id)
            stats.updated = result.updated
            stats.errors += result.errors
            _print_push_errors(result, config)
            if result.errors:
                stats.partial = True
            _upload_bundles(pusher, result, _artifacts)
        # Resource artifacts are digested but never uploaded: Logion does
        # not host another ecosystem's plugins.
        for batch in (resource_plan.create, resource_plan.update):
            if not batch:
                continue
            result = pusher.push_batch(batch, run_id=run_id)
            stats.created += result.created
            stats.updated += result.updated
            stats.errors += result.errors
            _print_push_errors(result, config)
            if result.errors:
                stats.partial = True

        if progress:
            progress.checkpoint("completed", status="completed")
        pusher.close_run(stats)
        _print_stats(stats)
        return 1 if stats.partial else 0  # noqa: TRY300 - terminal receipt is emitted above.
    except Exception:
        stats.partial = True
        if progress:
            progress.checkpoint("completed", status="failed")
        if pusher:
            _close_run_safely(pusher, stats)
        raise


def _close_run_safely(pusher: Pusher, stats: RunStats) -> None:
    """Attempt terminal persistence without replacing the pipeline failure."""
    try:
        pusher.close_run(stats)
    except Exception as exc:
        print(
            f"indexer-progress close-error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )


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


def cmd_validate_ai_catalog(
    config: IndexerConfig, args: argparse.Namespace
) -> int:
    """Validate an AI Catalog document for conformance."""
    import json as json_mod

    from .ai_catalog.v1_0.conformance import validate_document

    source = args.file_or_url
    if source.startswith(("http://", "https://")):
        transport = _build_transport(config)
        resp = transport.get(source)
        if resp.status != 200:
            print(f"fetch failed: HTTP {resp.status}", file=sys.stderr)
            return 1
        doc = json_mod.loads(resp.body.decode("utf-8"))
    else:
        with open(source) as fh:
            doc = json_mod.load(fh)

    result = validate_document(doc)
    print(f"conformance: {result.result}")
    print(f"level: {result.level}")
    for warning in result.warnings:
        print(f"  warning: {warning}")
    for error in result.errors:
        print(f"  error: {error}", file=sys.stderr)
    return 0 if result.passed else 1


def cmd_validate_ard(config: IndexerConfig, args: argparse.Namespace) -> int:
    """Validate an ARD search response for conformance."""
    import json as json_mod

    from .ard.v0_9.conformance import validate_search_response

    source = args.file_or_url
    if source.startswith(("http://", "https://")):
        transport = _build_transport(config)
        resp = transport.get(source)
        if resp.status != 200:
            print(f"fetch failed: HTTP {resp.status}", file=sys.stderr)
            return 1
        doc = json_mod.loads(resp.body.decode("utf-8"))
    else:
        with open(source) as fh:
            doc = json_mod.load(fh)

    result = validate_search_response(doc)
    print(f"conformance: {result.result}")
    for warning in result.warnings:
        print(f"  warning: {warning}")
    for error in result.errors:
        print(f"  error: {error}", file=sys.stderr)
    return 0 if result.passed else 1


def cmd_search(config: IndexerConfig, args: argparse.Namespace) -> int:
    """Search an ARD registry and print results."""
    from .adapters.ard import ARDAdapter

    transport = _build_transport(config)
    adapter = ARDAdapter(transport=transport)
    result = adapter.search(
        args.registry,
        query_text=args.query or "",
        page_size=args.page_size or 10,
    )
    if result.errors:
        for error in result.errors:
            print(f"error: {error}", file=sys.stderr)
    if args.json:
        print(json.dumps(_search_envelope(args, result), indent=2))
    else:
        print(f"results: {len(result.resources)}")
        for r in result.resources:
            print(f"  {r.canonical_uri} — {r.title}")
        if result.referrals:
            print(f"referrals: {len(result.referrals)}")
            for url in result.referrals:
                print(f"  {url}")
    return 1 if result.errors else 0


def _search_envelope(
    args: argparse.Namespace,
    result: object,
) -> dict[str, object]:
    """Wrap the hits in the context that makes them auditable later.

    A saved result set is only evidence if it says who was asked and
    what they were asked; the hits alone cannot be checked against
    either.
    """
    return {
        "registry": {"origin": args.registry},
        "query": {
            "text": args.query or "",
            "page_size": args.page_size or 10,
            "filters": {},
        },
        "results": [
            _search_result_json(r)
            for r in result.resources  # type: ignore[attr-defined]
        ],
        "referrals": result.referrals,  # type: ignore[attr-defined]
        "page_token": result.page_token,  # type: ignore[attr-defined]
        "errors": result.errors,  # type: ignore[attr-defined]
    }


def _search_result_json(resource: DiscoveredResource) -> dict:
    """Serialize one ARD hit without dropping where it came from.

    The score and the answering registry live in channel metadata, and
    a reader that only sees identifier/title/type cannot tell a hit from
    a trusted registry apart from one a stranger returned -- nor can it
    check that a score was registry-supplied metadata rather than
    something Logion inferred. Both claims are in the plan; neither
    survives a projection that keeps only the names.
    """
    channels = [
        {
            "hub_slug": channel.hub_slug,
            "hub_url": channel.hub_url,
            "metadata": dict(channel.metadata),
        }
        for channel in resource.channels
    ]
    metadata = dict(resource.channels[0].metadata) if resource.channels else {}
    return {
        "identifier": resource.canonical_uri,
        "title": resource.title,
        "resource_type": resource.resource_type,
        # Registry-supplied, never Logion's judgement. Absent rather
        # than zero when the registry did not send one: a missing score
        # and a score of zero are different answers.
        "score": metadata.get("relevance_score"),
        "source": metadata.get("ard_source")
        or (resource.channels[0].hub_url if resource.channels else None),
        "channels": channels,
    }


def cmd_ard_connectors(config: IndexerConfig, args: argparse.Namespace) -> int:
    """Manage pinned ard-connectors snapshots (operator command)."""
    from .sources.ard_connectors import ARDConnectorsSource

    transport = _build_transport(config)
    source = ARDConnectorsSource(
        transport=transport,
        source_url=getattr(args, "source_url", None),
    )

    subcommand = args.ard_connectors_command

    if subcommand == "sync":
        snapshot = source.fetch_snapshot(
            commit_sha=getattr(args, "commit", None)
        )
        if not snapshot.is_valid:
            print(f"sync: failed — {snapshot.validation_error}")
            return 1
        print("sync: ok")
        print(f"  repo: {snapshot.repo}")
        print(f"  commit: {snapshot.commit_sha}")
        print(f"  digest: {snapshot.file_digest}")
        print(f"  finders: {len(snapshot.finders)}")
        for f in snapshot.finders:
            print(f"    {f.id}: {f.name} — {f.search}")
        # Fetching and validating a directory the node then forgets is
        # not a sync. Recording it is what makes the pinned set
        # answerable later, by anyone other than this process.
        return _record_snapshot(config, transport, source, snapshot)

    if subcommand == "diff":
        # Fetch two snapshots and diff them.
        old_commit = args.old_commit
        new_commit = args.new_commit
        old_snap = source.fetch_snapshot(commit_sha=old_commit)
        new_snap = source.fetch_snapshot(commit_sha=new_commit)
        diff = source.diff_snapshots(old_snap, new_snap)
        if not diff.has_changes:
            print("diff: no changes")
            return 0
        print("diff:")
        if diff.added:
            print(f"  added: {', '.join(diff.added)}")
        if diff.removed:
            print(f"  removed: {', '.join(diff.removed)}")
        if diff.changed:
            print(f"  changed: {', '.join(diff.changed)}")
        return 0

    if subcommand == "approve":
        # In a real deployment this writes an approval record.
        # For the CLI, just print the action.
        print(f"approve: {args.finder_id}")
        return 0

    if subcommand == "status":
        snapshot = source.fetch_snapshot(
            commit_sha=getattr(args, "commit", None)
        )
        print(f"status: {snapshot.status}")
        print(f"  commit: {snapshot.commit_sha}")
        print(f"  digest: {snapshot.file_digest}")
        if snapshot.validation_error:
            print(f"  error: {snapshot.validation_error}")
        print(f"  finders: {len(snapshot.finders)}")
        return 0

    print(f"unknown ard-connectors subcommand: {subcommand}")
    return 1


def cmd_agent_finders(config: IndexerConfig, args: argparse.Namespace) -> int:
    """Run Agent Finder queries (operator command)."""
    from .sources.agent_finders import AgentFindersSource
    from .sources.ard_connectors import ARDConnectorsSource

    transport = _build_transport(config)
    # The directory this run queries has to be the one the node pinned.
    # Defaulting to upstream means `sync` pins one set and `run` queries
    # another, while every record still reports a snapshot commit -- the
    # pin becomes decoration.
    connectors = ARDConnectorsSource(
        transport=transport,
        source_url=getattr(args, "source_url", None),
    )
    snapshot = connectors.fetch_snapshot(
        commit_sha=getattr(args, "commit", None)
    )
    if not snapshot.is_valid:
        print(f"snapshot invalid: {snapshot.validation_error}")
        return 1

    finders_source = AgentFindersSource(transport=transport)
    approved: set[str] | None = None
    if args.finder and args.finder != "all":
        approved = {args.finder}

    result = finders_source.run(
        snapshot,
        query_text=args.query or "",
        approved_finder_ids=approved,
        max_results=args.limit or 100,
    )

    # --dry-run says "do not commit", not "do not report". It used to
    # return before the --json branch, so `--dry-run --json` printed
    # three lines of prose and every caller parsing it got nothing.
    if args.json:
        _print_agent_finders_json(result, dry_run=bool(args.dry_run))
    elif args.dry_run:
        _print_agent_finders_dry_run(result)
    else:
        _print_agent_finders_text(result)
    if args.dry_run:
        return 0
    return 1 if result.errors else 0


def _record_snapshot(
    config: IndexerConfig,
    transport: Transport,
    source: object,
    snapshot: object,
) -> int:
    """Persist the fetched snapshot against the node's registry."""
    url = f"{config.api_base_url.rstrip('/')}/v1/ard/sources"
    body = {
        "source_type": "ard-connectors",
        "source_uri": getattr(source, "source_url", None)
        or getattr(source, "file_path", "agent-finders.json"),
        "upstream_repo": snapshot.repo,  # type: ignore[attr-defined]
        "commit_sha": snapshot.commit_sha,  # type: ignore[attr-defined]
        "file_digest": snapshot.file_digest,  # type: ignore[attr-defined]
        # The registry's word for "fetched, parsed, safe to activate".
        "validation_result": "fresh",
        "last_good": True,
    }
    transport.set_api_base_url(config.api_base_url)
    resp = transport.post(url, json_body=body)
    if resp.status not in (200, 201):
        print(
            f"sync: fetched and validated, but the registry refused the "
            f"record (HTTP {resp.status})",
            file=sys.stderr,
        )
        return 1
    print("  recorded: last-good snapshot")
    return 0


def _print_agent_finders_dry_run(result: object) -> None:
    """Print a dry-run summary of agent finder query results."""
    print(f"dry-run: {len(result.resources)} resources")  # type: ignore[attr-defined]
    print(f"  finders queried: {len(result.records)}")  # type: ignore[attr-defined]
    print(f"  referrals: {len(result.referrals)}")  # type: ignore[attr-defined]


def _print_agent_finders_json(
    result: object,
    *,
    dry_run: bool = False,
) -> None:
    """Print agent finder results as JSON."""
    output = {
        "dry_run": dry_run,
        "finder_count": len(result.records),  # type: ignore[attr-defined]
        "resources": [
            {
                "identifier": r.canonical_uri,
                "title": r.title,
                "resource_type": r.resource_type,
            }
            for r in result.resources  # type: ignore[attr-defined]
        ],
        "records": [
            {
                "finder_id": rec.finder_id,
                "endpoint": rec.endpoint,
                "snapshot_commit": rec.snapshot_commit,
                "query_text_digest": rec.query_text_digest,
                "result_identifiers": list(rec.result_identifiers),
                "relevance_scores": [list(s) for s in rec.relevance_scores],
                "error": rec.error,
            }
            for rec in result.records  # type: ignore[attr-defined]
        ],
        "referrals": result.referrals,  # type: ignore[attr-defined]
        "errors": result.errors,  # type: ignore[attr-defined]
    }
    print(json.dumps(output, indent=2))


def _print_agent_finders_text(result: object) -> None:
    """Print agent finder results as human-readable text."""
    print(f"resources: {len(result.resources)}")  # type: ignore[attr-defined]
    for r in result.resources:  # type: ignore[attr-defined]
        print(f"  {r.canonical_uri} — {r.title}")
    print(f"records: {len(result.records)}")  # type: ignore[attr-defined]
    for rec in result.records:  # type: ignore[attr-defined]
        status = "ok" if not rec.error else f"error: {rec.error}"
        print(f"  {rec.finder_id}: {status}")
    if result.referrals:  # type: ignore[attr-defined]
        print(f"referrals: {len(result.referrals)}")  # type: ignore[attr-defined]


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
    crawl_parser.add_argument(
        "--adapter",
        default=None,
        help=(
            "run only this adapter (e.g. ai-catalog, ard, smithery). "
            "Shorthand for --only."
        ),
    )
    crawl_parser.add_argument(
        "--entrypoint",
        default=None,
        help=(
            "entrypoint URL for ai-catalog or ard adapter "
            "(overrides seed file target)"
        ),
    )
    crawl_parser.add_argument(
        "--report",
        default=None,
        help="write the import report (counters and quarantine) here",
    )
    crawl_parser.add_argument(
        "--ingest",
        action="store_true",
        help=(
            "record the discovered entries as resources with catalog "
            "provenance (ai-catalog adapter only)"
        ),
    )
    crawl_parser.add_argument(
        "--allow-quarantine",
        action="store_true",
        help=(
            "exit 0 even when entries were quarantined; without it a "
            "partial import is a documented failure"
        ),
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

    # validate-ai-catalog
    vac_parser = subparsers.add_parser(
        "validate-ai-catalog",
        help="validate an AI Catalog document for conformance",
    )
    vac_parser.add_argument(
        "file_or_url",
        help="path or URL to the AI Catalog JSON document",
    )

    # validate-ard
    vard_parser = subparsers.add_parser(
        "validate-ard",
        help="validate an ARD search response for conformance",
    )
    vard_parser.add_argument(
        "file_or_url",
        help="path or URL to the ARD search response JSON",
    )

    # search --adapter ard
    search_parser = subparsers.add_parser(
        "search",
        help="search an ARD registry",
    )
    search_parser.add_argument(
        "--adapter",
        default="ard",
        help="search adapter (default: ard)",
    )
    # Same reason as `agent-finders run`: every other flag here is local,
    # so `search ... --json` is what gets typed. argparse leaves an
    # already-set namespace attribute alone.
    search_parser.add_argument(
        "--json",
        action="store_true",
        help="output as JSON",
    )
    search_parser.add_argument(
        "--registry",
        required=True,
        help="ARD registry base URL",
    )
    search_parser.add_argument(
        "--query",
        default=None,
        help="natural-language search query",
    )
    search_parser.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="max results per page",
    )

    # ard-connectors sync|diff|approve|status
    ac_parser = subparsers.add_parser(
        "ard-connectors",
        help="manage pinned ard-connectors snapshots (operator)",
    )
    ac_sub = ac_parser.add_subparsers(
        dest="ard_connectors_command", required=True
    )
    ac_sync = ac_sub.add_parser("sync", help="fetch and pin latest snapshot")
    ac_sync.add_argument("--commit", default=None, help="specific commit SHA")
    ac_sync.add_argument(
        "--source-url",
        default=None,
        help=(
            "fetch the directory from this URL instead of the upstream "
            "repository (the digest still pins the content)"
        ),
    )
    ac_diff = ac_sub.add_parser("diff", help="diff two snapshots")
    ac_diff.add_argument("old_commit", help="old commit SHA")
    ac_diff.add_argument("new_commit", help="new commit SHA")
    ac_approve = ac_sub.add_parser("approve", help="approve a finder")
    ac_approve.add_argument("finder_id", help="finder ID to approve")
    ac_status = ac_sub.add_parser("status", help="show snapshot status")
    ac_status.add_argument(
        "--commit", default=None, help="specific commit SHA"
    )
    ac_status.add_argument(
        "--source-url", default=None, help="read the directory from this URL"
    )

    # agent-finders run
    af_parser = subparsers.add_parser(
        "agent-finders",
        help="run Agent Finder queries (operator)",
    )
    af_sub = af_parser.add_subparsers(
        dest="agent_finders_command", required=True
    )
    af_run = af_sub.add_parser("run", help="query enabled finders")
    # `--json` is global, but every other flag on this command is local,
    # so `... run --dry-run --json` is what anyone writes first. argparse
    # leaves an already-set namespace attribute alone, so accepting it
    # here does not clobber the global form.
    af_run.add_argument(
        "--json",
        action="store_true",
        help="output as JSON",
    )
    af_run.add_argument(
        "--source-url",
        default=None,
        help="query the finder directory pinned from this URL",
    )
    af_run.add_argument(
        "--finder",
        default="all",
        help="finder ID or 'all' (default: all)",
    )
    af_run.add_argument(
        "--query-family",
        default=None,
        help="query family (unused, reserved for future)",
    )
    af_run.add_argument(
        "--query",
        default="",
        help="discovery query text",
    )
    af_run.add_argument(
        "--commit",
        default=None,
        help="specific snapshot commit SHA",
    )
    af_run.add_argument(
        "--dry-run",
        action="store_true",
        help="plan only, no side effects",
    )

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
    elif args.command == "validate-ai-catalog":
        sys.exit(cmd_validate_ai_catalog(config, args))
    elif args.command == "validate-ard":
        sys.exit(cmd_validate_ard(config, args))
    elif args.command == "search":
        sys.exit(cmd_search(config, args))
    elif args.command == "ard-connectors":
        sys.exit(cmd_ard_connectors(config, args))
    elif args.command == "agent-finders":
        sys.exit(cmd_agent_finders(config, args))
    else:
        parser.print_help()
        sys.exit(1)

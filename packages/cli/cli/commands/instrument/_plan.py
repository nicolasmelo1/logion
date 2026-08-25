# SPDX-License-Identifier: MIT
"""Plan building, dry-run rendering, and execution for ``logion instrument``.

Extracted from ``handlers.py`` to keep the handler module under the
250-line limit enforced by the architecture test. API resolution
lives in ``_resolve.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cli._errors import handle_validation_error
from cli._json import (
    JsonObject,
    require_object_array,
    require_str_array,
)
from cli._output import emit_json

from ._capability import resolve_capability
from ._digest import profile_digest
from ._display import print_diff, print_plan
from ._projection import INTEGRATION_VERSION, build_projection
from ._resolve import resource_slug
from ._write import build_default_profile, execute_projection


def resolve_profile(
    args: argparse.Namespace,
    resource: JsonObject,
    version: JsonObject,
    events: list[str],
    publisher_identity: str,
    json_output: bool,
) -> JsonObject | None:
    """Load or build the instrumentation profile. Returns None on error."""
    profile_path = getattr(args, "profile", None)
    if profile_path is not None:
        return json.loads(Path(profile_path).read_text(encoding="utf-8"))
    delivery_endpoint = getattr(args, "delivery_endpoint", None)
    if not delivery_endpoint:
        handle_validation_error(
            "--delivery-endpoint is required when not using --profile",
            json_output=json_output,
        )
        return None
    return build_default_profile(
        resource=resource,
        version=version,
        events=events,
        delivery_endpoint=delivery_endpoint,
        delivery_mode=getattr(args, "delivery_mode", "asynchronous-batch"),
        max_batch=getattr(args, "max_batch", 20),
        max_spool_bytes=getattr(args, "max_spool_bytes", 262144),
        publisher_identity=publisher_identity,
    )


def profile_events(profile: JsonObject, fallback: list[str]) -> list[str]:
    """Return the events *profile* declares, in canonical order.

    Capability resolution has to answer "what did the publisher ask to
    observe", and the profile is where that lives. Falls back to the
    flag-derived list only when the profile names none, so a malformed
    profile cannot silently widen the ask.
    """
    declared = profile.get("events")
    if not isinstance(declared, list):
        return fallback
    events = [item for item in declared if isinstance(item, str)]
    return events or fallback


def validate_profile_if_available(profile: JsonObject) -> None:
    """Validate the profile if the instrumentation package is present."""
    try:
        # The validator accepts dict[str, object]; JsonObject is
        # dict[str, JsonValue]. The values are JSON-safe at runtime.
        from typing import cast

        from logion_instrumentation.validator import (
            validate_profile,
        )

        validate_profile(cast("dict[str, object]", profile))
    except ImportError:
        pass  # instrumentation package not installed in test env


def resolve_output_dir(
    args: argparse.Namespace,
    resource: JsonObject,
    version: JsonObject,
) -> Path:
    """Determine the output directory for projections."""
    output_dir = getattr(args, "output_dir", None)
    if output_dir is None:
        return Path.cwd() / resource_slug(resource, version)
    return Path(output_dir)


def build_plan(
    args: argparse.Namespace,
    resource: JsonObject,
    version: JsonObject,
    profile: JsonObject,
    publisher_identity: str,
    output_dir: Path,
    targets: list[str],
    events: list[str],
) -> JsonObject:
    """Build the full instrument plan with projections and capabilities."""
    prof_dig = profile_digest(profile)
    projections: list[JsonObject] = []
    capabilities: list[JsonObject] = []

    for target in targets:
        projections.append(
            build_projection(
                target=target,
                resource=resource,
                version=version,
                profile=profile,
                output_dir=output_dir,
                publisher_identity=publisher_identity,
            )
        )
        capabilities.append(
            resolve_capability(
                target=target,
                client=getattr(args, "client", None),
                events=events,
                profile_digest=prof_dig,
            )
        )

    blocked_reasons: list[str] = [
        f"{cap.get('client', '?')}: {cap.get('reason', 'unsupported')}"
        for cap in capabilities
        if cap.get("tier") == "unsupported"
    ]

    return {
        "resource_version": args.resource_version,
        "dry_run": bool(getattr(args, "dry_run", True)),
        "output_dir": str(output_dir),
        "publisher_identity": publisher_identity,
        "resource": resource,
        "version": version,
        "profile": profile,
        "profile_digest": prof_dig,
        "projections": projections,
        "capabilities": capabilities,
        "executable": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "confirmation_required": not bool(getattr(args, "yes", False)),
        "integration_version": INTEGRATION_VERSION,
    }


def render_dry_run(json_output: bool, plan: JsonObject) -> None:
    """Print the plan and diff for dry-run mode."""
    if json_output:
        emit_json("logion.instrument", plan)
    else:
        print_plan(plan)
        sys.stdout.write("\n")
        print_diff(plan)


def execute_plan(
    args: argparse.Namespace,
    config: object,
    plan: JsonObject,
    resource: JsonObject,
    version: JsonObject,
    profile: JsonObject,
    publisher_identity: str,
) -> int:
    """Execute the approved plan — approval-gated, writes files."""
    json_output = getattr(config, "json_output", False)
    if not plan["executable"]:
        blocked = require_str_array(plan, "blocked_reasons")
        return handle_validation_error(
            "instrument plan is not executable: " + "; ".join(blocked),
            json_output=json_output,
        )
    if not getattr(args, "yes", False):
        if not sys.stdin.isatty():
            return handle_validation_error(
                "instrument write requires --yes in "
                "non-interactive mode after reviewing the plan",
                json_output=json_output,
            )
        answer = input("Proceed with instrument write? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            if json_output:
                emit_json("logion.instrument", {"declined": True})
            else:
                sys.stdout.write("Declined. No files written.\n")
            return 0

    projections = require_object_array(plan, "projections")
    capabilities = require_object_array(plan, "capabilities")
    results: list[JsonObject] = []
    for proj, cap in zip(projections, capabilities, strict=True):
        results.append(
            execute_projection(
                proj,
                resource=resource,
                version=version,
                profile=profile,
                publisher_identity=publisher_identity,
                capability=cap,
            )
        )

    receipt_payload: JsonObject = {
        "resource_version": plan["resource_version"],
        "output_dir": plan["output_dir"],
        "publisher_identity": publisher_identity,
        "results": results,
        "integration_version": INTEGRATION_VERSION,
    }
    if json_output:
        emit_json("logion.instrument.executed", receipt_payload)
    else:
        sys.stdout.write(
            f"Instrumented {len(results)} projection(s) into "
            f"{plan['output_dir']}\n"
        )
        for result in results:
            mark = "✓" if result.get("verified") else "✗"
            sys.stdout.write(
                f"  {mark} [{result['target']}] {result['projection_root']}\n"
            )
    return 0

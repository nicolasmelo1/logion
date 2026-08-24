# SPDX-License-Identifier: MIT
"""Human-readable rendering for instrument plans and diffs."""

from __future__ import annotations

import sys

from cli._json import JsonObject, children, elements


def print_plan(plan: JsonObject) -> None:
    """Print an instrument generation plan for interactive CLI users."""
    out = sys.stdout
    out.write(f"Resource Version: {plan['resource_version']}\n")
    out.write(f"Dry-run:          {plan['dry_run']}\n")
    out.write(f"Output directory:  {plan.get('output_dir', '(default)')}\n")
    out.write(f"\nPublisher: {plan.get('publisher_identity', '?')}\n")

    resource = _nested(plan, "resource")
    if resource:
        out.write(
            f"Resource:  {resource.get('canonical_uri', '?')} "
            f"[{resource.get('resource_type', '?')}] — "
            f"{resource.get('title', '')}\n"
        )

    version = _nested(plan, "version")
    if version:
        out.write(
            f"Version:   {version.get('version', version.get('id', '?'))}\n"
        )

    profile = _nested(plan, "profile")
    if profile:
        out.write(
            "\nInstrumentation profile:\n"
            f"  schema:              {profile.get('schema', '?')}\n"
            "  integration_version: "
            f"{profile.get('integration_version', '?')}\n"
            f"  events:              {profile.get('events', [])}\n"
            f"  fields:              {profile.get('fields', [])}\n"
            f"  excluded:            {profile.get('excluded', [])}\n"
        )

    out.write("\nProjections:\n")
    for proj in children(plan, "projections"):
        out.write(f"\n  [{proj['target']}]\n")
        out.write(f"    slug:           {proj.get('slug', '?')}\n")
        out.write(f"    projection root: {proj.get('projection_root', '?')}\n")
        out.write(
            "    distribution_digest: "
            f"{proj.get('distribution_digest', '?')}\n"
        )
        out.write(
            f"    integration_version: "
            f"{proj.get('integration_version', '?')}\n"
        )
        receipt = _nested(proj, "receipt")
        if receipt:
            out.write(
                f"    receipt publisher: "
                f"{_nested(receipt, 'publisher').get('identity', '?')}\n"
            )
            out.write(
                f"    receipt version:   "
                f"{receipt.get('resource_version', '?')}\n"
            )
        out.write("    files:\n")
        for entry in children(proj, "files"):
            out.write(
                f"      {entry.get('role', '?')}: {entry.get('path', '?')}\n"
            )

    capabilities = children(plan, "capabilities")
    if capabilities:
        out.write("\nCapabilities:\n")
        for cap in capabilities:
            out.write(f"\n  [{cap.get('target', '?')}]\n")
            out.write(f"    tier:     {cap.get('tier', '?')}\n")
            out.write(f"    client:   {cap.get('client', '?')}\n")
            out.write(f"    binding:  {cap.get('reporter_binding', '?')}\n")
            runtime = _nested(cap, "reporter_runtime")
            out.write(
                f"    runtime:  required={runtime.get('required', '?')}, "
                f"present={runtime.get('present', '?')}\n"
            )
            if cap.get("reason"):
                out.write(f"    reason:   {cap['reason']}\n")

    out.write(
        f"\nExecutable: {plan.get('executable', '?')}\n"
        f"Confirmation required: {plan.get('confirmation_required', '?')}\n"
    )
    for reason in elements(plan, "blocked_reasons"):
        out.write(f"  blocked: {reason}\n")

    out.write("\nRules enforced:\n")
    out.write("  - Portable core copied byte-identical (digest-verified)\n")
    out.write("  - Every receipt names the original publisher and version\n")
    out.write(
        "  - Projection carries distribution_digest and integration_version\n"
    )
    out.write(
        "  - No package published, no permissions widened, "
        "no network delivery enabled\n"
    )


def print_diff(plan: JsonObject) -> None:
    """Print a diff of what would change if the plan were executed."""
    out = sys.stdout
    out.write("=== Projection diff (dry-run) ===\n\n")
    for proj in children(plan, "projections"):
        out.write(f"[{proj['target']}]\n")
        out.write(
            f"  distribution_digest: {proj.get('distribution_digest', '?')}\n"
        )
        for entry in children(proj, "files"):
            out.write(f"  + {entry.get('path', '?')}\n")
        out.write("\n")
    out.write("No files written. Pass --no-dry-run --yes to execute.\n")


def _nested(obj: JsonObject, key: str) -> JsonObject:
    """Return ``obj[key]`` as a JsonObject, or empty dict."""
    value = obj.get(key)
    return value if isinstance(value, dict) else {}

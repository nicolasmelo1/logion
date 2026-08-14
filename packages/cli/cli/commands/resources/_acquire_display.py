# SPDX-License-Identifier: MIT
"""Human-readable acquisition-plan rendering."""

from __future__ import annotations

import sys
from typing import Any


def print_plan(plan: dict[str, Any]) -> None:
    """Print an acquisition plan for interactive CLI users."""
    out = sys.stdout
    out.write(f"Resource: {plan['resource_id']}\n")
    out.write(f"Scope:    {plan['scope']}\n")
    out.write(f"Harness:  {plan['harness']}\n")
    out.write(f"Dry-run:  {plan['dry_run']}\n")
    if plan.get("default_scope_for_cwd"):
        out.write(f"Default scope for CWD: {plan['default_scope_for_cwd']}\n")
    out.write("\nTargets:\n")
    for target in plan["targets"]:
        out.write(
            f"  [{target['scope_kind']}] {target['installation_path']} "
            f"({target['state']})\n"
        )
        if target.get("native_manager"):
            out.write(f"    native manager: {target['native_manager']}\n")
        operation = target["operation"]
        out.write(
            f"    operation: {operation['kind']} "
            f"(ready={operation['ready']})\n"
        )
    if plan.get("resource"):
        resource = plan["resource"]
        canonical = resource.get("canonical_uri", plan["resource_id"])
        out.write(
            f"\nResource: {canonical} "
            f"[{resource.get('resource_type', '?')}] — "
            f"{resource.get('title', '')}\n"
        )
    if plan.get("versions"):
        out.write("\nVersions:\n")
        for version in plan["versions"]:
            out.write(
                f"  {version.get('id', version.get('version_id', '?'))}\n"
            )
    _print_distribution(out, plan)
    observation = plan.get("observation_integration", {})
    out.write(
        f"\nObservation: {observation.get('integration_version', '?')} "
        f"(consent={observation.get('consent', '?')}, "
        f"spool={observation.get('spool_enabled')})\n"
    )
    out.write(
        f"\nPermissions required: {plan.get('permissions_required')}\n"
        f"Confirmation required: {plan.get('confirmation_required')}\n"
        f"Executable: {plan.get('executable')}\n"
    )
    for reason in plan.get("blocked_reasons") or []:
        out.write(f"  blocked: {reason}\n")


def _print_distribution(out: Any, plan: dict[str, Any]) -> None:
    """Render the server-owned distribution the execution path would use."""
    distribution = plan.get("distribution") or {}
    if not distribution.get("resolved"):
        out.write(
            "\nDistribution: unresolved "
            f"({distribution.get('reason', 'unknown')})\n"
        )
        return
    native = distribution.get("native") or {}
    license_info = distribution.get("license") or {}
    entitlement = distribution.get("entitlement") or {}
    out.write("\nDistribution:\n")
    out.write(f"  channel:     {distribution.get('channel')}\n")
    alternatives = distribution.get("alternatives") or []
    if alternatives:
        out.write(f"  alternatives: {', '.join(alternatives)}\n")
    out.write(f"  digest:      {distribution.get('content_digest')}\n")
    out.write(
        f"  license:     {license_info.get('spdx') or 'unknown'} "
        f"(redistributable={license_info.get('redistribution_allowed')})\n"
    )
    if entitlement.get("required"):
        out.write(f"  entitlement: {entitlement.get('status')}\n")
    if distribution.get("expected_bytes") is not None:
        out.write(
            f"  bytes:       {distribution['expected_bytes']} "
            f"({distribution.get('expected_files')} file(s))\n"
        )
    if native.get("tool"):
        out.write(
            f"  native tool: {native['tool']} "
            f"{native.get('tested_version') or '?'}\n"
        )
    if native.get("argv"):
        # Displayed as the exact argv list; never a shell string.
        out.write(f"  argv:        {native['argv']}\n")
    if native.get("upstream_locator"):
        out.write(f"  upstream:    {native['upstream_locator']}\n")
    if native.get("revision"):
        out.write(f"  revision:    {native['revision']}\n")
    permissions = distribution.get("permissions") or {}
    out.write(
        f"  permissions: network={permissions.get('network')} "
        f"tools={permissions.get('tools')} "
        f"secrets={permissions.get('secrets')}\n"
    )
    verification = plan.get("verification") or {}
    out.write(
        f"  verification expectation: "
        f"{verification.get('expected_level', 'unknown')}\n"
    )
    for warning in distribution.get("warnings") or []:
        out.write(f"  warning:     {warning}\n")

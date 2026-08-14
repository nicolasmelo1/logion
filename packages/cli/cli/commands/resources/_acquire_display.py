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
    observation = plan.get("observation_integration", {})
    out.write(
        f"\nObservation: {observation.get('integration_version', '?')} "
        f"(consent={observation.get('consent', '?')}, "
        f"spool={observation.get('spool_enabled')})\n"
    )
    out.write(
        f"\nPermissions required: {plan.get('permissions_required')}\n"
        f"Confirmation required: {plan.get('confirmation_required')}\n"
    )

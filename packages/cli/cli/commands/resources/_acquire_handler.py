# SPDX-License-Identifier: MIT
"""Handler for ``logion resources acquire`` (dry-run only in 15.9.1).

Produces a zero-write acquisition plan showing the resolved scope target,
resource/version/distribution details, the native argv or copy operation,
digest/provenance status, observation integration state, and the
permissions/confirmation required.  The non-dry run requires explicit
approval and is not implemented in this phase.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._harness.scopes import (
    CUSTOM,
    SYSTEM,
    USER,
    canonical_scope,
    default_scope_for_cwd,
    is_valid_scope,
)
from cli._output import emit_json, to_data

from ._acquire_plan import build_plan, normalize_resource, normalize_versions
from ._inventory_handler import _all_scan_targets
from ._scope_resolution import resolve_acquire_targets


def handle_resources_acquire(args: argparse.Namespace) -> int:
    """Execute ``logion resources acquire RESOURCE_ID --dry-run``."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        if not bool(getattr(args, "dry_run", True)):
            sys.stderr.write(
                "resource acquisition is not implemented; "
                "no files were written\n"
            )
            return 2
        cwd_raw = getattr(args, "cwd", None)
        cwd = Path(cwd_raw).resolve() if cwd_raw else Path.cwd().resolve()
        default_scope = default_scope_for_cwd(cwd)
        explicit_scope = getattr(args, "scope", None)
        scope = explicit_scope or (
            USER if default_scope == CUSTOM else default_scope
        )
        if not is_valid_scope(scope):
            sys.stderr.write(f"unknown scope: {scope!r}\n")
            return 2
        scope = canonical_scope(scope)
        if scope == SYSTEM:
            sys.stderr.write(
                "scope 'system' is inventory-only and cannot be acquired\n"
            )
            return 2
        harness = getattr(args, "harness", None)
        if harness is None:
            sys.stderr.write("--harness is required for acquire\n")
            return 2
        repo_root_raw = getattr(args, "repo_root", None)
        repo_root = Path(repo_root_raw).resolve() if repo_root_raw else None
        repo_parent_raw = getattr(args, "repo_parent", None)
        repo_parent = (
            Path(repo_parent_raw).resolve() if repo_parent_raw else None
        )
        target_path_raw = getattr(args, "target_path", None)
        target_path = (
            Path(target_path_raw).expanduser().resolve()
            if target_path_raw
            else None
        )
        targets = resolve_acquire_targets(
            harness,
            scope,
            cwd,
            repo_root,
            repo_parent=repo_parent,
            target_path=target_path,
        )
        if not targets:
            sys.stderr.write(
                f"harness {harness!r} does not support scope {scope!r}\n"
            )
            return 2
        visible_targets = _all_scan_targets(
            harness, cwd, repo_root, target_path
        )

        resource_payload = to_data(
            client.v1.resources.get(resource_id=args.resource_id)
        )
        resource = normalize_resource(resource_payload)
        version_payload = to_data(
            client.v1.resources.versions(resource_id=args.resource_id)
        )
        versions = normalize_versions(version_payload)
        plan = build_plan(
            resource_id=args.resource_id,
            scope=scope,
            harness=harness,
            resource=resource,
            versions=versions,
            targets=targets,
            default_scope=default_scope,
            scope_was_explicit=explicit_scope is not None,
            visible_targets=visible_targets,
        )
        if config.json_output:
            emit_json("logion.resources.acquire", plan)
        else:
            _print_plan(plan)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def _print_plan(plan: dict[str, Any]) -> None:
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
        r = plan["resource"]
        out.write(
            f"\nResource: {r.get('canonical_uri', plan['resource_id'])} "
            f"[{r.get('resource_type', '?')}] — {r.get('title', '')}\n"
        )
    if plan.get("versions"):
        out.write("\nVersions:\n")
        for v in plan["versions"]:
            out.write(f"  {v.get('id', v.get('version_id', '?'))}\n")
    obs = plan.get("observation_integration", {})
    out.write(
        f"\nObservation: {obs.get('integration_version', '?')} "
        f"(consent={obs.get('consent', '?')}, "
        f"spool={obs.get('spool_enabled')})\n"
    )
    out.write(
        f"\nPermissions required: {plan.get('permissions_required')}\n"
        f"Confirmation required: {plan.get('confirmation_required')}\n"
    )

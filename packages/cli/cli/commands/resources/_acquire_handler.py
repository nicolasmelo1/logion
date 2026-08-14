# SPDX-License-Identifier: MIT
"""Handler for ``logion resources acquire``.

Dry-run and execution share one plan. Both resolve the harness scope
locally, fetch the server-owned acquisition plan, and combine them, so the
zero-write preview shows exactly what execution would do: channel, native
argv, expected bytes, integrity pin, permissions, and the verification
level reachable. Execution then requires the plan to be executable and
explicitly approved.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, handle_validation_error
from cli._harness.scopes import (
    SYSTEM,
    canonical_scope,
    default_scope_for_cwd,
    is_valid_scope,
)
from cli._output import emit_json, to_data

from ._acquire_display import print_plan
from ._acquire_distribution import fetch_distribution
from ._acquire_exec import run_acquisition
from ._acquire_plan import (
    _resource_name,
    build_plan,
    normalize_resource,
    normalize_versions,
)
from ._inventory_handler import _all_scan_targets
from ._scope_resolution import resolve_acquire_targets


def handle_resources_acquire(args: argparse.Namespace) -> int:
    """Execute ``logion resources acquire RESOURCE_ID --dry-run``."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        cwd_raw = getattr(args, "cwd", None)
        cwd = Path(cwd_raw).resolve() if cwd_raw else Path.cwd().resolve()
        default_scope = default_scope_for_cwd(cwd)
        explicit_scope = getattr(args, "scope", None)
        scope = explicit_scope or default_scope
        if not is_valid_scope(scope):
            return handle_validation_error(
                f"unknown scope: {scope!r}", json_output=config.json_output
            )
        scope = canonical_scope(scope)
        if scope == SYSTEM:
            return handle_validation_error(
                "scope 'system' is inventory-only and cannot be acquired",
                json_output=config.json_output,
            )
        harness = getattr(args, "harness", None)
        if harness is None:
            return handle_validation_error(
                "--harness is required for acquire",
                json_output=config.json_output,
            )
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
            return handle_validation_error(
                f"harness {harness!r} does not support scope {scope!r}",
                json_output=config.json_output,
            )
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
        requested_version = getattr(args, "version", None)
        if requested_version:
            versions = [
                version
                for version in versions
                if str(version.get("id") or version.get("version_id"))
                == requested_version
            ]
            if not versions:
                return handle_validation_error(
                    "requested resource version was not found",
                    json_output=config.json_output,
                )
        requested_channel = str(getattr(args, "channel", "auto") or "auto")
        distribution, distribution_error = fetch_distribution(
            client,
            resource_id=args.resource_id,
            versions=versions,
            channel=requested_channel,
        )
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
            distribution=distribution,
            distribution_error=distribution_error,
        )
        if bool(getattr(args, "dry_run", True)):
            plan["dry_run"] = True
            if config.json_output:
                emit_json("logion.resources.acquire", plan)
            else:
                print_plan(plan)
            return 0
        plan["dry_run"] = False
        # `executable` is False whenever the distribution is unresolved, so
        # this also narrows `distribution` to a concrete plan.
        if not plan["executable"] or distribution is None:
            return handle_validation_error(
                "acquisition is not executable: "
                + "; ".join(plan["blocked_reasons"]),
                json_output=config.json_output,
            )
        return _execute_plan(
            args,
            config,
            client,
            plan,
            distribution=distribution,
            scope=scope,
            harness=harness,
            targets=targets,
            resource=resource,
            requested_channel=requested_channel,
        )
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    finally:
        client.close()


def _execute_plan(
    args: argparse.Namespace,
    config: Any,
    client: Any,
    plan: dict[str, Any],
    *,
    distribution: dict[str, Any],
    scope: str,
    harness: str,
    targets: list[Any],
    resource: dict[str, Any],
    requested_channel: str,
) -> int:
    """Execute the already-validated plan and persist the receipt."""
    server_plan = distribution
    selected = str(server_plan["selected_channel"])
    if requested_channel != "auto" and selected != requested_channel:
        return handle_validation_error(
            f"server selected channel {selected!r} but "
            f"{requested_channel!r} was requested; re-run with "
            f"--channel {selected} to approve it explicitly",
            json_output=config.json_output,
        )
    target = targets[0]
    name = _resource_name(resource, args.resource_id)
    destination = target.target_path / name
    relative = destination.relative_to(target.scope_root).as_posix()
    receipt = run_acquisition(
        client=client,
        plan={
            "resource_id": args.resource_id,
            "version_id": server_plan["version_id"],
            "distribution_id": server_plan["distribution_id"],
            "content_digest": server_plan["content_digest"],
            "selected_channel": selected,
            "license": server_plan.get("license") or {},
            "entitlement": server_plan.get("entitlement") or {},
            "expected": server_plan.get("expected") or {},
            "native": server_plan.get("native") or {},
            "permissions": server_plan.get("permissions") or {},
        },
        scope=scope,
        harness=harness,
        destination=destination,
        scope_root=target.scope_root,
        relative_target_path=relative,
        resource_type=str(resource.get("resource_type") or "agent_skill"),
        assume_yes=bool(getattr(args, "yes", False)),
        json_output=config.json_output,
    )
    if config.json_output:
        emit_json("logion.resources.acquire", receipt)
    else:
        sys.stdout.write(
            f"Installed {plan['resource_name']} via {selected} "
            f"(verification={receipt['verification']})\n"
        )
    return 0

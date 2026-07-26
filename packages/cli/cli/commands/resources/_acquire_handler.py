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
from cli._harness import get_adapter
from cli._harness.scopes import (
    REPO_ROOT,
    ScopeTarget,
    canonical_scope,
    default_scope_for_cwd,
    is_valid_scope,
)
from cli._observation import (
    INTEGRATION_VERSION,
    LOCAL_ONLY,
    ConsentConfig,
)
from cli._output import emit_json, to_data


def _resolve_targets(
    harness: str,
    scope: str,
    cwd: Path | None,
    repo_root: Path | None,
) -> list[ScopeTarget]:
    adapter = get_adapter(harness)
    if adapter is None:
        raise ValueError(f"unknown harness: {harness!r}")
    # Re-instantiate with cwd/repo_root if the adapter supports them.
    cls = type(adapter)
    kwargs: dict[str, Any] = {}
    if cwd is not None:
        kwargs["cwd"] = cwd
    if repo_root is not None:
        kwargs["repo_root"] = repo_root
    import contextlib

    with contextlib.suppress(TypeError):
        adapter = cls(**kwargs)  # type: ignore[arg-type]
    cscope = canonical_scope(scope)
    return adapter.scope_targets(cscope)


def _build_plan(
    *,
    resource_id: str,
    scope: str,
    harness: str,
    cwd: Path | None,
    repo_root: Path | None,  # noqa: ARG001
    resource: dict[str, Any] | None,
    versions: list[dict[str, Any]],
    targets: list[ScopeTarget],
    dry_run: bool,
) -> dict[str, Any]:
    cscope = canonical_scope(scope)
    consent = ConsentConfig(level=LOCAL_ONLY)
    plan: dict[str, Any] = {
        "resource_id": resource_id,
        "scope": cscope,
        "harness": harness,
        "dry_run": dry_run,
        "observation_integration": {
            "integration_version": INTEGRATION_VERSION,
            "consent": consent.level,
            "spool_enabled": True,
        },
        "targets": [
            {
                "scope_kind": t.scope_kind,
                "scope_root": str(t.scope_root),
                "target_path": str(t.target_path),
                "native_manager": t.native_manager,
                "exists": t.exists,
            }
            for t in targets
        ],
        "resource": resource,
        "versions": versions,
        "default_scope_for_cwd": (
            default_scope_for_cwd(Path(cwd)) if cwd else None
        ),
        "permissions_required": True,
        "confirmation_required": True,
    }
    return plan


def handle_resources_acquire(args: argparse.Namespace) -> int:
    """Execute ``logion resources acquire RESOURCE_ID --dry-run``."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        scope = getattr(args, "scope", None) or REPO_ROOT
        if not is_valid_scope(scope):
            sys.stderr.write(f"unknown scope: {scope!r}\n")
            return 2
        harness = getattr(args, "harness", None)
        if harness is None:
            sys.stderr.write("--harness is required for acquire\n")
            return 2
        cwd_raw = getattr(args, "cwd", None)
        cwd = Path(cwd_raw) if cwd_raw else None
        repo_root_raw = getattr(args, "repo_root", None)
        repo_root = Path(repo_root_raw) if repo_root_raw else None
        targets = _resolve_targets(harness, scope, cwd, repo_root)
        if not targets:
            sys.stderr.write(
                f"harness {harness!r} does not support scope {scope!r}\n"
            )
            return 2

        # Fetch resource + versions from the SDK (best-effort; the dry
        # run is still useful when the SDK is unreachable because the
        # plan is about local target resolution).
        resource: dict[str, Any] | None = None
        versions: list[dict[str, Any]] = []
        try:
            result = client.v1.resources.get(resource_id=args.resource_id)
            resource = to_data(result)
        except Exception:
            resource = None
        try:
            vresult = client.v1.resources.versions(
                resource_id=args.resource_id
            )
            vdata = to_data(vresult)
            if isinstance(vdata, list):
                versions = vdata
            elif isinstance(vdata, dict):
                versions = vdata.get("items", [])
        except Exception:
            versions = []

        plan = _build_plan(
            resource_id=args.resource_id,
            scope=scope,
            harness=harness,
            cwd=cwd,
            repo_root=repo_root,
            resource=resource,
            versions=versions,
            targets=targets,
            dry_run=bool(getattr(args, "dry_run", True)),
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
    for t in plan["targets"]:
        state = "exists" if t["exists"] else "will be created"
        out.write(f"  [{t['scope_kind']}] {t['target_path']} ({state})\n")
        if t.get("native_manager"):
            out.write(f"    native manager: {t['native_manager']}\n")
    if plan.get("resource"):
        r = plan["resource"]
        out.write(
            f"\nResource: {r.get('canonical', '?')} "
            f"[{r.get('resource_type', '?')}] — {r.get('title', '')}\n"
        )
    if plan.get("versions"):
        out.write("\nVersions:\n")
        for v in plan["versions"]:
            out.write(f"  {v.get('version_id', '?')}\n")
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

# SPDX-License-Identifier: MIT
"""Handler for ``logion resources inventory``.

Scans the harness's native skill locations and lists found resources with
reconciliation status:

- ``exact``    — native manager receipt/lock ID + immutable revision.
- ``canonical`` — canonical source + revision and content digest.
- ``signature-present-unverified`` — structurally valid signature marker whose
  publisher trust root has not been verified.
- ``ambiguous`` or ``unlinked`` — no exact evidence.

The scan is read-only and never modifies native locations.  Reconciliation
records the observed scope and does not move/reinstall content.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, cast

from cli._config import resolve_config_from_args
from cli._errors import handle_error, handle_validation_error
from cli._harness.custom import CustomPathHarness
from cli._harness.scopes import (
    ADMIN,
    CUSTOM,
    REPO_CURRENT,
    REPO_PARENT,
    REPO_ROOT,
    SYSTEM,
    USER,
    ScopeTarget,
)

from ._reconciliation import mark_ambiguities, reconciliation_status
from ._scope_resolution import git_root, instantiate_adapter


def _all_scan_targets(
    harness: str,
    cwd: Path | None,
    repo_root: Path | None,
    target_path: Path | None = None,
) -> list[ScopeTarget]:
    """Collect native targets in harness precedence order."""
    selected_cwd = (cwd or Path.cwd()).resolve()
    if harness == "custom":
        if target_path is None:
            raise ValueError("custom harness requires --target-path")
        return CustomPathHarness(target_path).scope_targets(CUSTOM)
    adapter = instantiate_adapter(harness, selected_cwd, repo_root)
    targets = list(adapter.scope_targets(REPO_CURRENT))
    root = repo_root or git_root(selected_cwd)
    if root is not None:
        root = root.resolve()
        try:
            selected_cwd.relative_to(root)
        except ValueError as exc:
            raise ValueError("CWD must be inside the repository root") from exc
    if root is not None and selected_cwd != root:
        parent = selected_cwd.parent
        while parent != root and parent != parent.parent:
            parent_adapter = instantiate_adapter(harness, parent, root)
            targets.extend(
                ScopeTarget(
                    scope_kind=REPO_PARENT,
                    scope_root=target.scope_root,
                    target_path=target.target_path,
                    native_manager=target.native_manager,
                    exists=target.exists,
                )
                for target in parent_adapter.scope_targets(REPO_CURRENT)
            )
            parent = parent.parent
    for scope in (REPO_ROOT, USER, ADMIN, SYSTEM):
        targets.extend(adapter.scope_targets(scope))
    legacy_skill_dir = getattr(adapter, "legacy_skill_dir", None)
    if callable(legacy_skill_dir):
        legacy_path = cast(Path, legacy_skill_dir())
        targets.append(
            ScopeTarget(
                scope_kind="legacy",
                scope_root=legacy_path.parent,
                target_path=legacy_path,
                native_manager=None,
                exists=legacy_path.exists(),
            )
        )
    seen: set[Path] = set()
    unique: list[ScopeTarget] = []
    for target in targets:
        resolved = target.target_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(target)
    return unique


def _scan_dir(target: ScopeTarget, precedence: int) -> list[dict[str, Any]]:
    """List skill directories under *target* with reconciliation status."""
    if not target.target_path.is_dir():
        return []
    found: list[dict[str, Any]] = []
    try:
        children = sorted(target.target_path.iterdir())
    except OSError:
        return []
    for child in children:
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        entry: dict[str, Any] = {
            "name": child.name,
            "path": str(child),
            "scope_kind": target.scope_kind,
            "scope_root": str(target.scope_root),
            "precedence": precedence,
            "reconciliation": reconciliation_status(child),
        }
        found.append(entry)
    return found


def handle_resources_inventory(args: argparse.Namespace) -> int:
    """Execute ``logion resources inventory --harness HARNESS``."""
    config = resolve_config_from_args(args)
    try:
        harness = getattr(args, "harness", None)
        if harness is None:
            return handle_validation_error(
                "--harness is required for inventory",
                json_output=config.json_output,
            )
        cwd_raw = getattr(args, "cwd", None)
        cwd = Path(cwd_raw).resolve() if cwd_raw else None
        repo_root_raw = getattr(args, "repo_root", None)
        repo_root = Path(repo_root_raw).resolve() if repo_root_raw else None
        target_path_raw = getattr(args, "target_path", None)
        target_path = (
            Path(target_path_raw).expanduser().resolve()
            if target_path_raw
            else None
        )
        targets = _all_scan_targets(harness, cwd, repo_root, target_path)
        requested_scope = str(getattr(args, "scope", "all") or "all")
        if requested_scope != "all":
            targets = [
                target
                for target in targets
                if target.scope_kind == requested_scope
                or (
                    requested_scope == REPO_ROOT
                    and target.scope_kind == REPO_CURRENT
                )
            ]
        results: list[dict[str, Any]] = []
        for precedence, target in enumerate(targets):
            results.extend(_scan_dir(target, precedence))
        mark_ambiguities(results)
        payload: dict[str, Any] = {
            "harness": harness,
            "scope": requested_scope,
            "targets": [
                {
                    "scope_kind": t.scope_kind,
                    "target_path": str(t.target_path),
                    "exists": t.exists,
                }
                for t in targets
            ],
            "resources": results,
            "count": len(results),
        }
        if config.json_output:
            from cli._output import emit_json

            emit_json("logion.resources.inventory", payload)
        else:
            _print_inventory(payload)
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    else:
        return 0


def _print_inventory(payload: dict[str, Any]) -> None:
    out = sys.stdout
    out.write(f"Harness: {payload['harness']}\n")
    out.write("\nScanned targets:\n")
    for t in payload["targets"]:
        state = "exists" if t["exists"] else "missing"
        out.write(f"  [{t['scope_kind']}] {t['target_path']} ({state})\n")
    out.write(f"\nFound {payload['count']} resource(s):\n")
    for r in payload["resources"]:
        recon = r["reconciliation"]
        out.write(
            f"  {r['name']} [{r['scope_kind']}] — {recon['status']} "
            f"(digest={recon['content_digest'][:12]}...)\n"
        )

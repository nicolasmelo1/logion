# SPDX-License-Identifier: MIT
"""Handler for ``logion resources inventory``.

Scans the harness's native skill locations and lists found resources with
reconciliation status:

- ``exact``    — native manager receipt/lock ID + immutable revision.
- ``canonical`` — canonical source + revision and content digest.
- ``signed``   — signed bundle/resource digest.
- ``ambiguous`` or ``unlinked`` — no exact evidence.

The scan is read-only and never modifies native locations.  Reconciliation
records the observed scope and does not move/reinstall content.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

from cli._config import resolve_config_from_args
from cli._errors import handle_error
from cli._harness import get_adapter
from cli._harness.scopes import (
    REPO_CURRENT,
    REPO_PARENT,
    REPO_ROOT,
    USER,
    ScopeTarget,
)


def _all_scan_targets(
    harness: str,
    cwd: Path | None,
    repo_root: Path | None,
) -> list[ScopeTarget]:
    """Collect every scope target the harness declares for repo + user."""
    adapter = get_adapter(harness)
    if adapter is None:
        raise ValueError(f"unknown harness: {harness!r}")
    cls = type(adapter)
    kwargs: dict[str, Any] = {}
    if cwd is not None:
        kwargs["cwd"] = cwd
    if repo_root is not None:
        kwargs["repo_root"] = repo_root
    import contextlib

    with contextlib.suppress(TypeError):
        adapter = cls(**kwargs)  # type: ignore[arg-type]
    targets: list[ScopeTarget] = []
    for scope in (REPO_CURRENT, REPO_PARENT, REPO_ROOT, USER):
        targets.extend(adapter.scope_targets(scope))
    # De-duplicate by target_path while preserving order.
    seen: set[Path] = set()
    unique: list[ScopeTarget] = []
    for t in targets:
        if t.target_path in seen:
            continue
        seen.add(t.target_path)
        unique.append(t)
    return unique


def _scan_dir(target: ScopeTarget) -> list[dict[str, Any]]:
    """List skill directories under *target* with reconciliation status."""
    if not target.target_path.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for child in sorted(target.target_path.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        entry: dict[str, Any] = {
            "name": child.name,
            "path": str(child),
            "scope_kind": target.scope_kind,
            "reconciliation": _reconciliation_status(child),
        }
        found.append(entry)
    return found


def _reconciliation_status(skill_dir: Path) -> dict[str, str]:
    """Compute the reconciliation status for a discovered skill dir.

    implements the structural scan only: a content digest is
    computed for SKILL.md and the status defaults to ``unlinked`` unless a
    native manager receipt or canonical manifest is present.  The full
    exact/canonical/signed evidence chain is filled in by later phases.
    """
    skill_md = skill_dir / "SKILL.md"
    digest = ""
    if skill_md.is_file():
        digest = hashlib.sha256(skill_md.read_bytes()).hexdigest()
    status = "unlinked"
    # A native manager receipt (e.g. a lock file) would mark it exact.
    if (skill_dir / ".logion-lock.json").is_file():
        status = "exact"
    elif (skill_dir / ".logion-manifest.json").is_file():
        status = "canonical"
    elif (skill_dir / ".logion-sig.json").is_file():
        status = "signed"
    return {"status": status, "content_digest": digest}


def handle_resources_inventory(args: argparse.Namespace) -> int:
    """Execute ``logion resources inventory --harness HARNESS``."""
    config = resolve_config_from_args(args)
    try:
        harness = getattr(args, "harness", None)
        if harness is None:
            sys.stderr.write("--harness is required for inventory\n")
            return 2
        cwd_raw = getattr(args, "cwd", None)
        cwd = Path(cwd_raw) if cwd_raw else None
        repo_root_raw = getattr(args, "repo_root", None)
        repo_root = Path(repo_root_raw) if repo_root_raw else None
        targets = _all_scan_targets(harness, cwd, repo_root)
        results: list[dict[str, Any]] = []
        for t in targets:
            results.extend(_scan_dir(t))
        payload: dict[str, Any] = {
            "harness": harness,
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
        return handle_error(exc)
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

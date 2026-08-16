# SPDX-License-Identifier: MIT
"""Shared scope resolution for resource acquisition and inventory."""

from __future__ import annotations

import inspect
from pathlib import Path

from cli._harness import get_adapter
from cli._harness.base import HarnessAdapter
from cli._harness.custom import CustomPathHarness
from cli._harness.scopes import (
    CUSTOM,
    REPO_CURRENT,
    REPO_PARENT,
    ScopeTarget,
    canonical_scope,
)
from cli._json import JsonObject


def instantiate_adapter(
    harness: str,
    cwd: Path,
    repo_root: Path | None,
) -> HarnessAdapter:
    adapter = get_adapter(harness)
    if adapter is None:
        raise ValueError(f"unknown harness: {harness!r}")
    cls = type(adapter)
    parameters = inspect.signature(cls).parameters
    kwargs: JsonObject = {}
    if "cwd" in parameters:
        kwargs["cwd"] = cwd
    if repo_root is not None and "repo_root" in parameters:
        kwargs["repo_root"] = repo_root
    return cls(**kwargs)


def resolve_acquire_targets(
    harness: str,
    scope: str,
    cwd: Path,
    repo_root: Path | None,
    *,
    repo_parent: Path | None = None,
    target_path: Path | None = None,
) -> list[ScopeTarget]:
    canonical = canonical_scope(scope)
    if harness == "custom":
        if canonical != CUSTOM or target_path is None:
            raise ValueError(
                "custom harness requires --scope custom and --target-path"
            )
        return CustomPathHarness(target_path).scope_targets(CUSTOM)
    if canonical == CUSTOM:
        raise ValueError(
            "scope custom requires --harness custom --target-path"
        )
    selected_cwd = cwd
    selected_scope = canonical
    if canonical == REPO_PARENT:
        if repo_parent is None:
            raise ValueError("repo-parent scope requires --repo-parent")
        root = repo_root or git_root(cwd)
        if root is None or not is_strict_ancestor(repo_parent, cwd, root):
            raise ValueError(
                "--repo-parent must be between the CWD and repository root"
            )
        selected_cwd = repo_parent
        selected_scope = REPO_CURRENT
    adapter = instantiate_adapter(harness, selected_cwd, repo_root)
    targets = adapter.scope_targets(selected_scope)
    if canonical != REPO_PARENT:
        return targets
    return [
        ScopeTarget(
            scope_kind=REPO_PARENT,
            scope_root=target.scope_root,
            target_path=target.target_path,
            native_manager=target.native_manager,
            exists=target.exists,
        )
        for target in targets
    ]


def git_root(cwd: Path) -> Path | None:
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def is_strict_ancestor(parent: Path, cwd: Path, root: Path) -> bool:
    resolved_parent = parent.resolve()
    resolved_cwd = cwd.resolve()
    resolved_root = root.resolve()
    if resolved_parent in {resolved_cwd, resolved_root}:
        return False
    try:
        resolved_cwd.relative_to(resolved_parent)
        resolved_parent.relative_to(resolved_root)
    except ValueError:
        return False
    return True

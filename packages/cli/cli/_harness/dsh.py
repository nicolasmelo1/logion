# SPDX-License-Identifier: MIT
"""Fail-closed scope adapter for the DeepSeek Harness CLI."""

from __future__ import annotations

import shutil
from pathlib import Path

from cli._harness.base import GrantResult, HarnessAdapter
from cli._harness.scopes import (
    REPO_CURRENT,
    REPO_PARENT,
    REPO_ROOT,
    USER,
    ScopeTarget,
    canonical_scope,
)

SUPPORTED_DSH_VERSION = "0.1.0-rc.6"
DSH_HOME_ENV = "DSH_HOME"


def _git_root(cwd: Path) -> Path | None:
    path = cwd.resolve()
    while True:
        if (path / ".git").exists():
            return path
        if path.parent == path:
            return None
        path = path.parent


class DshAdapter(HarnessAdapter):
    """DeepSeek Harness adapter with no observation capability.

    The native manager owns profile manifests and plugin configuration.  This
    adapter only declares isolated roots; it never edits a profile or loads a
    plugin.  Unknown manager versions are intentionally not accepted here.
    """

    name = "dsh"
    display_name = "DeepSeek Harness"
    manager_version = SUPPORTED_DSH_VERSION
    observation = "unsupported"

    def __init__(
        self,
        *,
        home_dir: Path | None = None,
        cwd: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._home_dir = home_dir
        self._cwd = cwd
        self._repo_root = repo_root

    def _home(self) -> Path:
        return self._home_dir if self._home_dir is not None else Path.home()

    def _cwd_path(self) -> Path:
        return self._cwd or Path.cwd()

    def _repo_root_path(self) -> Path | None:
        return self._repo_root or _git_root(self._cwd_path())

    @staticmethod
    def _target(scope: str, root: Path) -> ScopeTarget:
        target = root / ".dsh"
        return ScopeTarget(scope, root, target, "dsh", target.exists())

    def scope_targets(self, scope: str) -> list[ScopeTarget]:
        scope = canonical_scope(scope)
        cwd = self._cwd_path().resolve()
        repo = self._repo_root_path()
        if scope == USER:
            return [self._target(USER, self._home())]
        if scope == REPO_CURRENT:
            if repo is None:
                return []
            return [self._target(REPO_CURRENT, cwd)]
        if scope == REPO_PARENT:
            if repo is None or cwd.parent == repo:
                return []
            try:
                cwd.relative_to(repo)
            except ValueError:
                return []
            return [self._target(REPO_PARENT, cwd.parent)]
        if scope == REPO_ROOT:
            return [self._target(REPO_ROOT, repo)] if repo else []
        return []

    def is_present(self) -> bool:
        return shutil.which("dsh") is not None

    def config_path(self, scope: str) -> Path:
        targets = self.scope_targets(scope)
        return (
            (targets[0].target_path / "profiles" / "default" / "package.json")
            if targets
            else self._home()
            / ".dsh"
            / "profiles"
            / "default"
            / "package.json"
        )

    def is_granted(self, scope: str) -> bool:  # noqa: ARG002
        return False

    def grant(self, scope: str) -> GrantResult:
        return GrantResult(
            self.name,
            canonical_scope(scope),
            self.config_path(scope),
            changed=False,
            already=True,
        )

    def revoke(self, scope: str) -> GrantResult:
        return GrantResult(
            self.name,
            canonical_scope(scope),
            self.config_path(scope),
            changed=False,
            already=True,
        )

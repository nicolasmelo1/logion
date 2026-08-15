# SPDX-License-Identifier: MIT
"""Fail-closed scope adapter for the DeepSeek Harness CLI."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
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

#: The dsh release this adapter's state formats have been recorded
#: against. dsh is a developer preview that announces compatibility-
#: breaking changes, so an unrecognised version fails closed rather than
#: reading a format it was never tested on.
SUPPORTED_DSH_VERSION = "0.1.0-rc.6"

#: dsh resolves its harness home from this variable; profiles live in
#: ``$DSH_HOME/profiles/<name>``. Pointing it at a scope root is the only
#: way an install stays inside one repository.
DSH_HOME_ENV = "DSH_HOME"

#: The harness home directory name Logion pins a scope to.
DSH_HOME_DIRNAME = ".dsh"

_VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")


class UnsupportedDshVersionError(RuntimeError):
    """Raised when the installed dsh is not the pinned tested release."""


def dsh_home_for(scope_root: Path) -> Path:
    """Return the harness home a scope root owns."""
    return scope_root / DSH_HOME_DIRNAME


def detect_dsh_version(executable: str = "dsh") -> str | None:
    """Return the installed dsh version, or None when it cannot be read."""
    path = shutil.which(executable)
    if path is None:
        return None
    try:
        completed = subprocess.run(
            [path, "--version"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode:
        return None
    output = (completed.stdout or completed.stderr or b"").decode(
        errors="replace"
    )
    match = _VERSION_RE.search(output)
    return match.group(0) if match else None


def require_supported_dsh(executable: str = "dsh") -> str:
    """Return the installed version, or fail closed with a stable error."""
    version = detect_dsh_version(executable)
    if version is None:
        raise UnsupportedDshVersionError(
            "resource_native_tool_unsupported: dsh was not found or did "
            "not report a version"
        )
    if version != SUPPORTED_DSH_VERSION:
        raise UnsupportedDshVersionError(
            "resource_native_tool_version_unsupported: dsh "
            f"{version} is not the tested {SUPPORTED_DSH_VERSION}"
        )
    return version


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

    The native manager owns profile manifests and plugin configuration.
    This adapter only declares isolated harness homes; it never edits a
    profile or loads a plugin. Unknown manager versions are intentionally
    not accepted here.
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
        if self._home_dir is not None:
            return self._home_dir
        # A user-scope install belongs wherever dsh itself would put it,
        # so an operator who already moved their harness home keeps one
        # harness home instead of gaining a second, Logion-only one.
        configured = os.environ.get(DSH_HOME_ENV)
        if configured:
            return Path(configured).parent
        return Path.home()

    def _cwd_path(self) -> Path:
        return self._cwd or Path.cwd()

    def _repo_root_path(self) -> Path | None:
        return self._repo_root or _git_root(self._cwd_path())

    @staticmethod
    def _target(scope: str, root: Path) -> ScopeTarget:
        target = dsh_home_for(root)
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
        return detect_dsh_version() == SUPPORTED_DSH_VERSION

    def config_path(self, scope: str) -> Path:
        targets = self.scope_targets(scope)
        root = (
            targets[0].target_path if targets else dsh_home_for(self._home())
        )
        return root / "profiles" / "default" / "package.json"

    def is_granted(self, scope: str) -> bool:
        """A dsh scope is usable as soon as its harness home exists.

        There is nothing for Logion to grant: dsh reads
        ``$DSH_HOME`` and the acquisition passes it explicitly.
        """
        targets = self.scope_targets(scope)
        return bool(targets) and targets[0].target_path.is_dir()

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

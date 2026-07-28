# SPDX-License-Identifier: MIT
"""Hermes Agent harness adapter.

Hermes stores its configuration in ``~/.hermes/config.yaml`` (YAML, not
JSON) and loads skills from ``~/.hermes/skills/``.  Permission gating is
controlled by ``approvals.mode`` (``manual`` / ``smart`` / ``off``), and
Hermes *does* keep a per-command allow list — ``command_allowlist`` in
config.yaml — but it is keyed on command name, so a sub-command-scoped
grant cannot be expressed without over-granting all ``logion`` commands.

Therefore the autopost grant is a **no-op** for Hermes.

Scope targets :

- ``user`` → ``$HOME/.hermes/skills`` (active profile home).
- ``repo-root`` → ``$REPO_ROOT/.agents/skills`` (shared target,
  registered as an external directory for the isolated Hermes profile).
- Other repo scopes resolve to ``.agents/skills`` under the matching
  directory.
"""

from __future__ import annotations

import os
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


def _git_root(cwd: Path) -> Path | None:
    """Walk up from *cwd* looking for a ``.git`` dir/file."""
    path = Path(cwd).resolve()
    while True:
        if (path / ".git").exists():
            return path
        if path.parent == path:
            return None
        path = path.parent


class HermesAdapter(HarnessAdapter):
    """Hermes agent harness.

    User skills resolve to ``$HOME/.hermes/skills`` (the active
    profile's skill directory).  Repository-scope installs use the
    shared ``.agents/skills`` target and are registered as Hermes
    external directories.  Autopost grant is a no-op.
    """

    name = "hermes"
    display_name = "Hermes"

    def __init__(
        self,
        *,
        project_dir: Path | None = None,
        home_dir: Path | None = None,
        cwd: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._project_dir = project_dir
        self._home_dir = home_dir
        self._cwd = cwd
        self._repo_root = repo_root

    def _home(self) -> Path:
        return self._home_dir if self._home_dir is not None else Path.home()

    def _hermes_home(self) -> Path:
        configured = os.environ.get("HERMES_HOME")
        if configured:
            return Path(configured).expanduser()
        return self._home() / ".hermes"

    def _cwd_path(self) -> Path:
        if self._cwd is not None:
            return Path(self._cwd)
        if self._project_dir is not None:
            return Path(self._project_dir)
        return Path.cwd()

    def _repo_root_path(self) -> Path | None:
        if self._repo_root is not None:
            return Path(self._repo_root)
        return _git_root(self._cwd_path())

    # -- scope targets -----------------------------------------------------

    def scope_targets(self, scope: str) -> list[ScopeTarget]:
        cscope = canonical_scope(scope)
        cwd = self._cwd_path()
        repo_root = self._repo_root_path()

        if cscope == USER:
            hermes_home = self._hermes_home()
            target = hermes_home / "skills"
            return [
                ScopeTarget(
                    USER,
                    hermes_home,
                    target,
                    "hermes",
                    target.exists(),
                )
            ]
        if cscope == REPO_ROOT:
            if repo_root is None:
                return []
            # Shared cross-harness target; Hermes registers it as an
            # external directory for the isolated profile.
            target = repo_root / ".agents" / "skills"
            return [
                ScopeTarget(
                    REPO_ROOT, repo_root, target, None, target.exists()
                )
            ]
        if cscope == REPO_CURRENT:
            target = cwd / ".agents" / "skills"
            return [
                ScopeTarget(REPO_CURRENT, cwd, target, None, target.exists())
            ]
        if cscope == REPO_PARENT:
            if repo_root is None:
                return []
            parent = cwd.parent
            if parent == repo_root or not self._is_inside(cwd, repo_root):
                return []
            target = parent / ".agents" / "skills"
            return [
                ScopeTarget(REPO_PARENT, parent, target, None, target.exists())
            ]
        # admin/system/custom unsupported by Hermes.
        return []

    @staticmethod
    def _is_inside(child: Path, root: Path) -> bool:
        try:
            child.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return True

    def skill_dir(self) -> Path:
        targets = self.scope_targets(USER)
        return targets[0].target_path

    def is_present(self) -> bool:
        import shutil

        return (
            self._hermes_home().is_dir() or shutil.which("hermes") is not None
        )

    def config_path(self, scope: str) -> Path:  # noqa: ARG002
        return self._hermes_home() / "config.yaml"

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

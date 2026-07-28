# SPDX-License-Identifier: MIT
"""Pi harness adapter.

Pi discovers skills from:

- project ``.pi/skills`` and ``.agents/skills`` from CWD through the
  repository root;
- user ``$HOME/.pi/agent/skills`` and ``$HOME/.agents/skills``;
- package-provided skills and explicit configured/CLI paths (not modelled
  here — those are ephemeral attachments and retain package identity).

Cross-harness repo/user installs prefer ``.agents/skills``;
``.pi/skills`` is used only for Pi-specific content.  Autopost grant is
a no-op because Pi does not expose a per-command permission list that
Logion can target with a sub-command-scoped grant.
"""

from __future__ import annotations

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


class PiAdapter(HarnessAdapter):
    """Pi agent harness.

    User skills resolve to both ``$HOME/.pi/agent/skills`` (Pi-specific)
    and ``$HOME/.agents/skills`` (cross-harness).  Repository scopes map
    to ``.agents/skills`` for cross-harness installs and ``.pi/skills``
    for Pi-specific content.  Autopost grant is a no-op.
    """

    name = "pi"
    display_name = "Pi"

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
        home = self._home()

        if cscope == USER:
            # Pi-specific and cross-harness user locations.
            pi_target = home / ".pi" / "agent" / "skills"
            agents_target = home / ".agents" / "skills"
            return [
                ScopeTarget(
                    USER, home, agents_target, None, agents_target.exists()
                ),
                ScopeTarget(USER, home, pi_target, "pi", pi_target.exists()),
            ]
        if cscope == REPO_ROOT:
            if repo_root is None:
                return []
            agents = repo_root / ".agents" / "skills"
            pi = repo_root / ".pi" / "skills"
            return [
                ScopeTarget(
                    REPO_ROOT, repo_root, agents, None, agents.exists()
                ),
                ScopeTarget(REPO_ROOT, repo_root, pi, "pi", pi.exists()),
            ]
        if cscope == REPO_CURRENT:
            agents = cwd / ".agents" / "skills"
            pi = cwd / ".pi" / "skills"
            return [
                ScopeTarget(REPO_CURRENT, cwd, agents, None, agents.exists()),
                ScopeTarget(REPO_CURRENT, cwd, pi, "pi", pi.exists()),
            ]
        if cscope == REPO_PARENT:
            if repo_root is None:
                return []
            parent = cwd.parent
            if parent == repo_root or not self._is_inside(cwd, repo_root):
                return []
            agents = parent / ".agents" / "skills"
            pi = parent / ".pi" / "skills"
            return [
                ScopeTarget(
                    REPO_PARENT, parent, agents, None, agents.exists()
                ),
                ScopeTarget(REPO_PARENT, parent, pi, "pi", pi.exists()),
            ]
        # admin/system/custom unsupported by Pi.
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

        if (self._home() / ".pi").is_dir():
            return True
        if (self._home() / ".agents").is_dir():
            return True
        return shutil.which("pi") is not None

    def config_path(self, scope: str) -> Path:  # noqa: ARG002
        return self._home() / ".pi" / "config.json"

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

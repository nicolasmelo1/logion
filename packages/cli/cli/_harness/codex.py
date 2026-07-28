# SPDX-License-Identifier: MIT
"""Codex harness adapter.

Codex scans ``.agents/skills`` from CWD through every parent up to the
repository root and loads user skills from ``$HOME/.agents/skills``.
The legacy ``~/.codex/skills`` location is detected as an unverified
legacy installation but never offered as the default install target.

Permission gating in Codex is controlled by ``approval_policy`` and
``sandbox_mode`` / ``default_permissions`` — there is no per-command
allow list like Claude Code's ``permissions.allow``.  Therefore the
autopost grant is a **no-op** for Codex.

Scope targets :

- ``repo-current`` → ``$CWD/.agents/skills/<skill>/``
- ``repo-parent``  → ``$SELECTED_PARENT/.agents/skills/<skill>/``
- ``repo-root``    → ``$REPO_ROOT/.agents/skills/<skill>/``
- ``user``         → ``$HOME/.agents/skills/<skill>/``
- ``admin``        → ``/etc/codex/skills/<skill>/``
- ``system``       → bundled by Codex; inventory only (no target path)
"""

from __future__ import annotations

from pathlib import Path

from cli._harness.base import GrantResult, HarnessAdapter
from cli._harness.scopes import (
    ADMIN,
    REPO_CURRENT,
    REPO_PARENT,
    REPO_ROOT,
    SYSTEM,
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


class CodexAdapter(HarnessAdapter):
    """Codex agent harness.

    User skills resolve to ``$HOME/.agents/skills`` (the cross-harness
    location); ``~/.codex/skills`` is legacy and detected only as an
    unverified installation.  Autopost grant is a no-op because Codex
    has no per-command permission list.
    """

    name = "codex"
    display_name = "Codex"

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

    # -- scope targets ------------------------------------------------------

    def scope_targets(self, scope: str) -> list[ScopeTarget]:
        cscope = canonical_scope(scope)
        cwd = self._cwd_path()
        repo_root = self._repo_root_path()
        home = self._home()

        if cscope == REPO_CURRENT:
            target = cwd / ".agents" / "skills"
            return [
                ScopeTarget(REPO_CURRENT, cwd, target, None, target.exists())
            ]
        if cscope == REPO_PARENT:
            # The explicitly selected parent between CWD and repo root.
            # Without an explicit selection we use the immediate parent
            # of CWD when it is inside a repo; otherwise empty.
            if repo_root is None:
                return []
            parent = cwd.parent
            if parent == repo_root or not self._is_inside(cwd, repo_root):
                return []
            target = parent / ".agents" / "skills"
            return [
                ScopeTarget(REPO_PARENT, parent, target, None, target.exists())
            ]
        if cscope == REPO_ROOT:
            if repo_root is None:
                return []
            target = repo_root / ".agents" / "skills"
            return [
                ScopeTarget(
                    REPO_ROOT, repo_root, target, None, target.exists()
                )
            ]
        if cscope == USER:
            target = home / ".agents" / "skills"
            return [ScopeTarget(USER, home, target, None, target.exists())]
        if cscope == ADMIN:
            root = Path("/etc/codex")
            target = root / "skills"
            return [ScopeTarget(ADMIN, root, target, "codex", target.exists())]
        if cscope == SYSTEM:
            # Bundled by Codex; inventory only — no writable target.
            return [
                ScopeTarget(
                    scope_kind=SYSTEM,
                    scope_root=Path("/usr/share/codex"),
                    target_path=Path("/usr/share/codex/skills"),
                    native_manager="codex",
                    exists=Path("/usr/share/codex/skills").exists(),
                )
            ]
        # repo-parent, custom, and unknown → empty (unsupported).
        return []

    @staticmethod
    def _is_inside(child: Path, root: Path) -> bool:
        try:
            child.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return True

    # -- legacy compatibility ----------------------------------------------

    def skill_dir(self) -> Path:
        """User skills live under ``$HOME/.agents/skills`` (cross-harness).

        The legacy ``~/.codex/skills`` path is *not* offered as the
        default install target.  Callers that need to detect the legacy
        location use :meth:`legacy_skill_dir`.
        """
        targets = self.scope_targets(USER)
        return targets[0].target_path

    def legacy_skill_dir(self) -> Path:
        """Legacy ``~/.codex/skills`` — detected, not installed into."""
        return self._home() / ".codex" / "skills"

    def is_present(self) -> bool:
        import shutil

        if (self._home() / ".codex").is_dir():
            return True
        if (self._home() / ".agents").is_dir():
            return True
        return shutil.which("codex") is not None

    def config_path(self, scope: str) -> Path:  # noqa: ARG002
        return self._home() / ".codex" / "config.toml"

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

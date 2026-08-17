# SPDX-License-Identifier: MIT
"""Claude Code harness adapter.

Claude Code gates a model's tool calls with an auto-mode classifier and
a ``permissions.allow`` list in ``settings.json``.  An explicit ``allow``
rule that matches a command pre-approves it, so the classifier never has
to judge it.  This adapter inserts exactly the autopost grant — nothing
broader — into that list.

Scope targets :

- ``repo-current`` / ``repo-parent`` / ``repo-root`` → the corresponding
  ``.claude/skills`` directory.
- ``user`` → ``$HOME/.claude/skills``.
- Plugin-provided resources retain plugin distribution identity.

Config scopes map to the two settings files Claude Code reads:
``project`` → ``<cwd>/.claude/settings.json`` and ``global`` →
``~/.claude/settings.json``.  ``project``/``global`` are accepted as
aliases for ``repo-root``/``user`` respectively.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from cli._harness.base import (
    AUTOPOST_COMMAND,
    GrantResult,
    HarnessAdapter,
    HarnessConfigError,
)
from cli._harness.scopes import (
    REPO_CURRENT,
    REPO_PARENT,
    REPO_ROOT,
    USER,
    ScopeTarget,
    canonical_scope,
)
from cli._json import JsonArray, JsonObject, child
from cli._local_state import _atomic_write_text


def _git_root(cwd: Path) -> Path | None:
    """Walk up from *cwd* looking for a ``.git`` dir/file."""
    path = Path(cwd).resolve()
    while True:
        if (path / ".git").exists():
            return path
        if path.parent == path:
            return None
        path = path.parent


def _autopost_matcher() -> str:
    """Render :data:`AUTOPOST_COMMAND` as a Bash matcher."""
    return f"Bash({' '.join(AUTOPOST_COMMAND)}:*)"


class ClaudeCodeAdapter(HarnessAdapter):
    """Grants the autopost command in Claude Code's ``settings.json``."""

    name = "claude-code"
    display_name = "Claude Code"

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

    # -- path resolution ---------------------------------------------------

    def _project(self) -> Path:
        if self._cwd is not None:
            return Path(self._cwd)
        return (
            self._project_dir if self._project_dir is not None else Path.cwd()
        )

    def _home(self) -> Path:
        return self._home_dir if self._home_dir is not None else Path.home()

    def _repo_root_path(self) -> Path | None:
        if self._repo_root is not None:
            return Path(self._repo_root)
        return _git_root(self._project())

    # -- scope targets -----------------------------------------------------

    def scope_targets(self, scope: str) -> list[ScopeTarget]:
        cscope = canonical_scope(scope)
        proj = self._project()
        repo_root = self._repo_root_path()
        home = self._home()

        if cscope == REPO_CURRENT:
            target = proj / ".claude" / "skills"
            return [
                ScopeTarget(REPO_CURRENT, proj, target, None, target.exists())
            ]
        if cscope == REPO_PARENT:
            if repo_root is None:
                return []
            parent = proj.parent
            if parent == repo_root or not self._is_inside(proj, repo_root):
                return []
            target = parent / ".claude" / "skills"
            return [
                ScopeTarget(REPO_PARENT, parent, target, None, target.exists())
            ]
        if cscope == REPO_ROOT:
            if repo_root is None:
                return []
            target = repo_root / ".claude" / "skills"
            return [
                ScopeTarget(
                    REPO_ROOT, repo_root, target, None, target.exists()
                )
            ]
        if cscope == USER:
            target = home / ".claude" / "skills"
            return [ScopeTarget(USER, home, target, None, target.exists())]
        # admin/system/custom unsupported by Claude Code.
        return []

    @staticmethod
    def _is_inside(child: Path, root: Path) -> bool:
        try:
            child.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return True

    # -- legacy config-path interface --------------------------------------

    def config_path(self, scope: str) -> Path:
        cscope = canonical_scope(scope)
        if cscope in ("repo-root", "repo-current", "repo-parent"):
            return self._project() / ".claude" / "settings.json"
        if cscope == "user":
            return self._home() / ".claude" / "settings.json"
        if scope not in ("project", "global") and cscope not in (
            "repo-root",
            "repo-current",
            "repo-parent",
            "user",
        ):
            raise ValueError(f"unknown scope: {scope!r}")
        # Accept legacy project/global directly.
        base = self._home() if scope == "global" else self._project()
        return base / ".claude" / "settings.json"

    def skill_dir(self) -> Path:
        targets = self.scope_targets(USER)
        return targets[0].target_path

    # -- detection ---------------------------------------------------------

    def is_present(self) -> bool:
        """True if a ``.claude`` dir (home/project) or ``claude`` on PATH."""
        if (self._home() / ".claude").is_dir():
            return True
        if (self._project() / ".claude").is_dir():
            return True
        return shutil.which("claude") is not None

    # -- config read/write -------------------------------------------------

    def _read_settings(self, path: Path) -> JsonObject:
        if not path.is_file():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise HarnessConfigError(
                f"cannot parse {path} — refusing to overwrite: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise HarnessConfigError(
                f"{path} is not a JSON object — refusing to overwrite"
            )
        return raw

    def _allow_list(self, settings: JsonObject, path: Path) -> JsonArray:
        perms = settings.setdefault("permissions", {})
        if not isinstance(perms, dict):
            raise HarnessConfigError(
                f"{path}: 'permissions' is not an object — refusing to edit"
            )
        allow = perms.setdefault("allow", [])
        if not isinstance(allow, list):
            raise HarnessConfigError(
                f"{path}: 'permissions.allow' is not a list — refusing to edit"
            )
        return allow

    def _write_settings(self, path: Path, settings: JsonObject) -> None:
        _atomic_write_text(
            path,
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        )

    # -- grant / revoke / query -------------------------------------------

    def is_granted(self, scope: str) -> bool:
        path = self.config_path(scope)
        settings = self._read_settings(path)
        perms = settings.get("permissions")
        if not isinstance(perms, dict):
            return False
        allow = perms.get("allow")
        if not isinstance(allow, list):
            return False
        return _autopost_matcher() in allow

    def grant(self, scope: str) -> GrantResult:
        path = self.config_path(scope)
        settings = self._read_settings(path)
        allow = self._allow_list(settings, path)
        matcher = _autopost_matcher()
        if matcher in allow:
            return GrantResult(
                self.name,
                canonical_scope(scope),
                path,
                changed=False,
                already=True,
            )
        allow.append(matcher)
        self._write_settings(path, settings)
        return GrantResult(
            self.name,
            canonical_scope(scope),
            path,
            changed=True,
            already=False,
        )

    def revoke(self, scope: str) -> GrantResult:
        path = self.config_path(scope)
        if not path.is_file():
            return GrantResult(
                self.name,
                canonical_scope(scope),
                path,
                changed=False,
                already=True,
            )
        settings = self._read_settings(path)
        allow = self._allow_list(settings, path)
        matcher = _autopost_matcher()
        if matcher not in allow:
            return GrantResult(
                self.name,
                canonical_scope(scope),
                path,
                changed=False,
                already=True,
            )
        permissions = child(settings, "permissions")
        permissions["allow"] = [m for m in allow if m != matcher]
        settings["permissions"] = permissions
        self._write_settings(path, settings)
        return GrantResult(
            self.name,
            canonical_scope(scope),
            path,
            changed=True,
            already=False,
        )

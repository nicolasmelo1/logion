# SPDX-License-Identifier: MIT
"""OpenCode harness adapter.

OpenCode stores its configuration in ``opencode.json`` (JSON with
comments — JSONC) and loads skills from ``~/.config/opencode/skills/``.
Permission gating uses a ``permission`` object where each tool name
maps to either a string action (``"allow"``, ``"ask"``, ``"deny"``) or
a granular object of pattern → action pairs.

Scope targets :

- ``repo-current`` / ``repo-parent`` / ``repo-root`` → the corresponding
  ``.config/opencode/skills`` (or ``.agents/skills``) directory.
- ``user`` → ``$HOME/.config/opencode/skills``.

For the autopost grant, this adapter writes a bash permission rule:
``"permission": {"bash": {"logion courses report-usage*": "allow"}}``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

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


def _autopost_pattern() -> str:
    """Render :data:`AUTOPOST_COMMAND` as an OpenCode bash pattern."""
    return " ".join(AUTOPOST_COMMAND) + "*"


class OpenCodeAdapter(HarnessAdapter):
    """Grants the autopost command in OpenCode's ``opencode.json``."""

    name = "opencode"
    display_name = "OpenCode"

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
            # OpenCode project skills live under .config/opencode/skills;
            # the cross-harness .agents/skills is also accepted.
            target = proj / ".config" / "opencode" / "skills"
            return [
                ScopeTarget(REPO_CURRENT, proj, target, None, target.exists())
            ]
        if cscope == REPO_PARENT:
            if repo_root is None:
                return []
            parent = proj.parent
            if parent == repo_root or not self._is_inside(proj, repo_root):
                return []
            target = parent / ".config" / "opencode" / "skills"
            return [
                ScopeTarget(REPO_PARENT, parent, target, None, target.exists())
            ]
        if cscope == REPO_ROOT:
            if repo_root is None:
                return []
            target = repo_root / ".config" / "opencode" / "skills"
            return [
                ScopeTarget(
                    REPO_ROOT, repo_root, target, None, target.exists()
                )
            ]
        if cscope == USER:
            target = home / ".config" / "opencode" / "skills"
            return [ScopeTarget(USER, home, target, None, target.exists())]
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
        if cscope == "user" or scope == "global":
            return self._home() / ".config" / "opencode" / "opencode.json"
        if (
            cscope in ("repo-root", "repo-current", "repo-parent")
            or scope == "project"
        ):
            return self._project() / "opencode.json"
        raise ValueError(f"unknown scope: {scope!r}")

    def skill_dir(self) -> Path:
        targets = self.scope_targets(USER)
        return targets[0].target_path

    def is_present(self) -> bool:
        if (self._home() / ".config" / "opencode").is_dir():
            return True
        return shutil.which("opencode") is not None

    # -- config read/write -------------------------------------------------

    def _read_config(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise HarnessConfigError(
                f"cannot read {path} — refusing to overwrite: {exc}"
            ) from exc
        cleaned = _strip_jsonc_comments(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise HarnessConfigError(
                f"cannot parse {path} — refusing to overwrite: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise HarnessConfigError(
                f"{path} is not a JSON object — refusing to overwrite"
            )
        return data

    def _write_config(self, path: Path, data: dict[str, Any]) -> None:
        _atomic_write_text(
            path,
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        )

    def _bash_perms(
        self, config: dict[str, Any], path: Path
    ) -> dict[str, str]:
        perms = config.setdefault("permission", {})
        if not isinstance(perms, dict):
            raise HarnessConfigError(
                f"{path}: 'permission' is not an object — refusing to edit"
            )
        bash = perms.setdefault("bash", {})
        if isinstance(bash, str):
            bash = {"*": bash}
            perms["bash"] = bash
        if not isinstance(bash, dict):
            raise HarnessConfigError(
                f"{path}: 'permission.bash' is not an object — "
                "refusing to edit"
            )
        return bash

    # -- grant / revoke / query -------------------------------------------

    def is_granted(self, scope: str) -> bool:
        path = self.config_path(scope)
        config = self._read_config(path)
        perms = config.get("permission")
        if not isinstance(perms, dict):
            return False
        bash = perms.get("bash")
        if not isinstance(bash, dict):
            return False
        return bash.get(_autopost_pattern()) == "allow"

    def grant(self, scope: str) -> GrantResult:
        path = self.config_path(scope)
        config = self._read_config(path)
        bash = self._bash_perms(config, path)
        pattern = _autopost_pattern()
        if bash.get(pattern) == "allow":
            return GrantResult(
                self.name,
                canonical_scope(scope),
                path,
                changed=False,
                already=True,
            )
        bash[pattern] = "allow"
        self._write_config(path, config)
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
        config = self._read_config(path)
        bash = self._bash_perms(config, path)
        pattern = _autopost_pattern()
        if bash.get(pattern) != "allow":
            return GrantResult(
                self.name,
                canonical_scope(scope),
                path,
                changed=False,
                already=True,
            )
        del bash[pattern]
        self._write_config(path, config)
        return GrantResult(
            self.name,
            canonical_scope(scope),
            path,
            changed=True,
            already=False,
        )


def _strip_jsonc_comments(text: str) -> str:
    """Remove ``//`` line comments and ``/* */`` block comments.

    Tracks string literals (single and double quotes) so ``//`` inside
    strings (e.g. URLs like ``https://...``) is preserved.
    """
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    string_char = ""

    while i < n:
        ch = text[i]

        if in_string:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == string_char:
                in_string = False
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = True
            string_char = ch
            result.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < n and not (
                    text[i] == "*" and text[i + 1] == "/"
                ):
                    i += 1
                i += 2
                continue

        result.append(ch)
        i += 1

    return "".join(result)

# SPDX-License-Identifier: MIT
"""Claude Code harness adapter.

Claude Code gates a model's tool calls with an auto-mode classifier and
a ``permissions.allow`` list in ``settings.json``.  An explicit ``allow``
rule that matches a command pre-approves it, so the classifier never has
to judge it.  This adapter inserts exactly the autopost grant — nothing
broader — into that list.

Scopes map to the two settings files Claude Code reads:

* ``project`` → ``<cwd>/.claude/settings.json``
* ``global``  → ``~/.claude/settings.json``
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from cli._harness.base import (
    AUTOPOST_COMMAND,
    VALID_SCOPES,
    GrantResult,
    HarnessAdapter,
    HarnessConfigError,
)
from cli._local_state import _atomic_write_text


def _autopost_matcher() -> str:
    """Render :data:`AUTOPOST_COMMAND` as a Claude Code Bash matcher.

    ``("logion", "courses", "report-usage")`` →
    ``Bash(logion courses report-usage:*)`` — the narrowest matcher that
    allows the command with any arguments and nothing else.
    """
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
    ) -> None:
        # Injected only by tests; production uses cwd / real home.
        self._project_dir = project_dir
        self._home_dir = home_dir

    # -- path resolution ---------------------------------------------------

    def _project(self) -> Path:
        return (
            self._project_dir if self._project_dir is not None else Path.cwd()
        )

    def _home(self) -> Path:
        return self._home_dir if self._home_dir is not None else Path.home()

    def config_path(self, scope: str) -> Path:
        if scope not in VALID_SCOPES:
            raise ValueError(f"unknown scope: {scope!r}")
        base = self._home() if scope == "global" else self._project()
        return base / ".claude" / "settings.json"

    # -- detection ---------------------------------------------------------

    def is_present(self) -> bool:
        """True if a ``.claude`` dir (home/project) or ``claude`` on PATH."""
        if (self._home() / ".claude").is_dir():
            return True
        if (self._project() / ".claude").is_dir():
            return True
        return shutil.which("claude") is not None

    # -- config read/write -------------------------------------------------

    def _read_settings(self, path: Path) -> dict[str, Any]:
        """Parse settings.json; refuse to proceed on malformed JSON.

        Returns ``{}`` when the file is absent.  Raises
        :class:`HarnessConfigError` when the file exists but is not a JSON
        object, so a grant never clobbers unreadable user settings.
        """
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

    def _allow_list(self, settings: dict[str, Any], path: Path) -> list[Any]:
        """Return the ``permissions.allow`` list, validating shape."""
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

    def _write_settings(self, path: Path, settings: dict[str, Any]) -> None:
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
                self.name, scope, path, changed=False, already=True
            )
        allow.append(matcher)
        self._write_settings(path, settings)
        return GrantResult(self.name, scope, path, changed=True, already=False)

    def revoke(self, scope: str) -> GrantResult:
        path = self.config_path(scope)
        if not path.is_file():
            return GrantResult(
                self.name, scope, path, changed=False, already=True
            )
        settings = self._read_settings(path)
        allow = self._allow_list(settings, path)
        matcher = _autopost_matcher()
        if matcher not in allow:
            return GrantResult(
                self.name, scope, path, changed=False, already=True
            )
        settings["permissions"]["allow"] = [m for m in allow if m != matcher]
        self._write_settings(path, settings)
        return GrantResult(self.name, scope, path, changed=True, already=False)

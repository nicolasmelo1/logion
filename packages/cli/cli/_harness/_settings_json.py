# SPDX-License-Identifier: MIT
"""Shared base for harnesses that store permissions in a ``settings.json``.

Claude Code, Codex, and OpenCode all use a JSON settings file with a
``permissions.allow`` list.  This base factors out the common
read/write/grant/revoke logic so each adapter only parameterizes the
config path and skill directory.
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
    """Render :data:`AUTOPOST_COMMAND` as a Bash matcher.

    ``("logion", "courses", "report-usage")`` →
    ``Bash(logion courses report-usage:*)``.
    """
    return f"Bash({' '.join(AUTOPOST_COMMAND)}:*)"


class SettingsJsonAdapter(HarnessAdapter):
    """Base for harnesses that gate commands via ``settings.json``.

    Subclasses provide :meth:`_config_basename` (relative to home or
    project) and :meth:`skill_dir`.
    """

    def __init__(
        self,
        *,
        project_dir: Path | None = None,
        home_dir: Path | None = None,
    ) -> None:
        self._project_dir = project_dir
        self._home_dir = home_dir

    # -- path resolution ---------------------------------------------------

    def _project(self) -> Path:
        return (
            self._project_dir
            if self._project_dir is not None
            else Path.cwd()
        )

    def _home(self) -> Path:
        return self._home_dir if self._home_dir is not None else Path.home()

    def _config_basename(self) -> Path:
        """Relative path of the settings file under home/project root.

        Override per harness (e.g. ``.claude/settings.json``).
        """
        raise NotImplementedError

    def config_path(self, scope: str) -> Path:
        if scope not in VALID_SCOPES:
            raise ValueError(f"unknown scope: {scope!r}")
        base = self._home() if scope == "global" else self._project()
        return base / self._config_basename()

    # -- detection ---------------------------------------------------------

    def _detect_dirs(self) -> list[Path]:
        """Dirs whose presence implies this harness is installed."""
        return []

    def _detect_bins(self) -> list[str]:
        """Binary names whose presence on PATH implies this harness."""
        return []

    def is_present(self) -> bool:
        if any(d.is_dir() for d in self._detect_dirs()):
            return True
        return any(
            shutil.which(b) is not None for b in self._detect_bins()
        )

    # -- config read/write -------------------------------------------------

    def _read_settings(self, path: Path) -> dict[str, Any]:
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

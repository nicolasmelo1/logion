# SPDX-License-Identifier: MIT
"""OpenCode harness adapter.

OpenCode stores its configuration in ``opencode.json`` (JSON with
comments — JSONC) and loads skills from ``~/.config/opencode/skills/``.
Permission gating uses a ``permission`` object where each tool name
maps to either a string action (``"allow"``, ``"ask"``, ``"deny"``) or
a granular object of pattern → action pairs.

For the autopost grant, this adapter writes a bash permission rule:

```
"permission": {
  "bash": {
    "logion courses report-usage*": "allow"
  }
}
```

Config file locations (precedence: project > global):
- ``project`` → ``<cwd>/opencode.json`` (or ``.opencode/opencode.json``)
- ``global``  → ``~/.config/opencode/opencode.json``
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
from cli._local_state import _atomic_write_text


def _autopost_pattern() -> str:
    """Render :data:`AUTOPOST_COMMAND` as an OpenCode bash pattern.

    ``("logion", "courses", "report-usage")`` →
    ``logion courses report-usage*``.
    """
    return " ".join(AUTOPOST_COMMAND) + "*"


class OpenCodeAdapter(HarnessAdapter):
    """Grants the autopost command in OpenCode's ``opencode.json``.

    OpenCode uses a JSON config (JSONC) with a ``permission`` object
    where bash commands are matched by pattern.  This adapter inserts
    exactly the autopost grant as a bash permission rule.
    """

    name = "opencode"
    display_name = "OpenCode"

    def __init__(
        self,
        *,
        project_dir: Path | None = None,
        home_dir: Path | None = None,
    ) -> None:
        self._project_dir = project_dir
        self._home_dir = home_dir

    def _project(self) -> Path:
        return (
            self._project_dir if self._project_dir is not None else Path.cwd()
        )

    def _home(self) -> Path:
        return self._home_dir if self._home_dir is not None else Path.home()

    def config_path(self, scope: str) -> Path:
        from cli._harness.base import VALID_SCOPES

        if scope not in VALID_SCOPES:
            raise ValueError(f"unknown scope: {scope!r}")
        # Global config lives under ~/.config/opencode/ (matching
        # skill_dir()/is_present()); the project config is opencode.json
        # at the project root.  A bare ~/opencode.json (the old global
        # path) is not where OpenCode reads its settings, so the grant
        # would have been written to a file OpenCode never loads.
        if scope == "global":
            return self._home() / ".config" / "opencode" / "opencode.json"
        return self._project() / "opencode.json"

    def skill_dir(self) -> Path:
        return self._home() / ".config" / "opencode" / "skills"

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
        # Strip JSONC comments before parsing.
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
            # ``"bash": "allow"`` → upgrade to granular object so we
            # can add our specific pattern without losing the global.
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
                self.name, scope, path, changed=False, already=True
            )
        bash[pattern] = "allow"
        self._write_config(path, config)
        return GrantResult(self.name, scope, path, changed=True, already=False)

    def revoke(self, scope: str) -> GrantResult:
        path = self.config_path(scope)
        if not path.is_file():
            return GrantResult(
                self.name, scope, path, changed=False, already=True
            )
        config = self._read_config(path)
        bash = self._bash_perms(config, path)
        pattern = _autopost_pattern()
        if bash.get(pattern) != "allow":
            return GrantResult(
                self.name, scope, path, changed=False, already=True
            )
        del bash[pattern]
        self._write_config(path, config)
        return GrantResult(self.name, scope, path, changed=True, already=False)


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
                # Escape — keep the next char literal.
                result.append(text[i + 1])
                i += 2
                continue
            if ch == string_char:
                in_string = False
            i += 1
            continue

        # Not in a string.
        if ch in ('"', "'"):
            in_string = True
            string_char = ch
            result.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                # Line comment — skip to end of line.
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if nxt == "*":
                # Block comment — skip to */.
                i += 2
                while i + 1 < n and not (
                    text[i] == "*" and text[i + 1] == "/"
                ):
                    i += 1
                i += 2  # skip the */
                continue

        result.append(ch)
        i += 1

    return "".join(result)

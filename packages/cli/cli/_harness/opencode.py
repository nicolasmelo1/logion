# SPDX-License-Identifier: MIT
"""OpenCode harness adapter."""

from __future__ import annotations

from pathlib import Path

from cli._harness._settings_json import SettingsJsonAdapter


class OpenCodeAdapter(SettingsJsonAdapter):
    """OpenCode agent harness."""

    name = "opencode"
    display_name = "OpenCode"

    def _config_basename(self) -> Path:
        return Path(".config") / "opencode" / "settings.json"

    def skill_dir(self) -> Path:
        return self._home() / ".config" / "opencode" / "skills"

    def is_present(self) -> bool:
        import shutil

        return (self._home() / ".config" / "opencode").is_dir() or (
            shutil.which("opencode") is not None
        )

# SPDX-License-Identifier: MIT
"""Codex harness adapter."""

from __future__ import annotations

from pathlib import Path

from cli._harness._settings_json import SettingsJsonAdapter


class CodexAdapter(SettingsJsonAdapter):
    """Codex agent harness."""

    name = "codex"
    display_name = "Codex"

    def _config_basename(self) -> Path:
        return Path(".agents") / "settings.json"

    def skill_dir(self) -> Path:
        return self._home() / ".agents" / "skills"

    def is_present(self) -> bool:
        import shutil

        return (self._home() / ".agents").is_dir() or (
            shutil.which("codex") is not None
        )

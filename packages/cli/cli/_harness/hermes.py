# SPDX-License-Identifier: MIT
"""Hermes harness adapter."""

from __future__ import annotations

from pathlib import Path

from cli._harness._settings_json import SettingsJsonAdapter


class HermesAdapter(SettingsJsonAdapter):
    """Hermes agent harness."""

    name = "hermes"
    display_name = "Hermes"

    def _config_basename(self) -> Path:
        return Path(".hermes") / "settings.json"

    def skill_dir(self) -> Path:
        return self._home() / ".hermes" / "skills"

    def is_present(self) -> bool:
        import shutil

        return (self._home() / ".hermes").is_dir() or (
            shutil.which("hermes") is not None
        )

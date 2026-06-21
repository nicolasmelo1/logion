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

from pathlib import Path

from cli._harness._settings_json import SettingsJsonAdapter


class ClaudeCodeAdapter(SettingsJsonAdapter):
    """Grants the autopost command in Claude Code's ``settings.json``."""

    name = "claude-code"
    display_name = "Claude Code"

    def _config_basename(self) -> Path:
        return Path(".claude") / "settings.json"

    def skill_dir(self) -> Path:
        return self._home() / ".claude" / "skills"

    # -- detection ---------------------------------------------------------

    def is_present(self) -> bool:
        """True if a ``.claude`` dir (home/project) or ``claude`` on PATH."""
        if (self._home() / ".claude").is_dir():
            return True
        if (self._project() / ".claude").is_dir():
            return True
        import shutil

        return shutil.which("claude") is not None

# SPDX-License-Identifier: MIT
"""Custom-path harness for explicit ``--agent-dir`` targets.

A ``CustomPathHarness`` is constructed on demand with an explicit
``skill_dir`` path (from ``--agent-dir`` or a prompt).  It is never
auto-detected, and its grant/revoke are no-ops because a bare directory
has no known permission format.
"""

from __future__ import annotations

from pathlib import Path

from cli._harness.base import GrantResult, HarnessAdapter


class CustomPathHarness(HarnessAdapter):
    """Harness backed by an explicit skill directory."""

    name = "custom"
    display_name = "Custom path"

    def __init__(self, skill_dir_path: Path) -> None:
        self._skill_dir = Path(skill_dir_path)

    def skill_dir(self) -> Path:
        return self._skill_dir

    def is_present(self) -> bool:
        return False

    def config_path(self, scope: str) -> Path:  # noqa: ARG002
        # No settings file for a custom directory.
        return self._skill_dir / "settings.json"

    def is_granted(self, scope: str) -> bool:  # noqa: ARG002
        return False

    def grant(self, scope: str) -> GrantResult:
        return GrantResult(
            self.name,
            scope,
            self.config_path(scope),
            changed=False,
            already=True,
        )

    def revoke(self, scope: str) -> GrantResult:
        return GrantResult(
            self.name,
            scope,
            self.config_path(scope),
            changed=False,
            already=True,
        )

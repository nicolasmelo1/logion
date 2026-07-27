# SPDX-License-Identifier: MIT
"""Custom-path harness for explicit ``--agent-dir`` targets.

A ``CustomPathHarness`` is constructed on demand with an explicit
``skill_dir`` path (from ``--agent-dir`` or a prompt).  It is never
auto-detected, and its grant/revoke are no-ops because a bare directory
has no known permission format.

The custom scope  maps to the explicit path; all other
scopes return empty target lists.
"""

from __future__ import annotations

from pathlib import Path

from cli._harness.base import GrantResult, HarnessAdapter
from cli._harness.scopes import CUSTOM, ScopeTarget, canonical_scope


class CustomPathHarness(HarnessAdapter):
    """Harness backed by an explicit skill directory."""

    name = "custom"
    display_name = "Custom path"

    def __init__(self, skill_dir_path: Path) -> None:
        self._skill_dir = Path(skill_dir_path)

    def scope_targets(self, scope: str) -> list[ScopeTarget]:
        cscope = canonical_scope(scope)
        if cscope == CUSTOM:
            return [
                ScopeTarget(
                    CUSTOM,
                    self._skill_dir.parent,
                    self._skill_dir,
                    None,
                    self._skill_dir.exists(),
                )
            ]
        # Aliases that callers may pass for the custom path.
        if scope in ("project", "global"):
            return []
        return []

    def skill_dir(self) -> Path:
        return self._skill_dir

    def is_present(self) -> bool:
        return False

    def config_path(self, scope: str) -> Path:  # noqa: ARG002
        return self._skill_dir / "settings.json"

    def is_granted(self, scope: str) -> bool:  # noqa: ARG002
        return False

    def grant(self, scope: str) -> GrantResult:
        return GrantResult(
            self.name,
            canonical_scope(scope),
            self.config_path(scope),
            changed=False,
            already=True,
        )

    def revoke(self, scope: str) -> GrantResult:
        return GrantResult(
            self.name,
            canonical_scope(scope),
            self.config_path(scope),
            changed=False,
            already=True,
        )

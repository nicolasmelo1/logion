# SPDX-License-Identifier: MIT
"""Codex harness adapter.

Codex stores its configuration in ``~/.codex/config.toml`` (TOML, not
JSON) and loads skills from ``~/.codex/skills/``.  Permission gating in
Codex is controlled by ``approval_policy`` and ``sandbox_mode`` /
``default_permissions`` — there is no per-command allow list like
Claude Code's ``permissions.allow``.  Codex uses a sandbox model that
controls *what* can run (filesystem + network), not *which* specific
commands are pre-approved.

Therefore the autopost grant is a **no-op** for Codex: ``grant`` and
``revoke`` report ``already=True`` without writing anything, and
``is_granted`` always returns ``False``.  The companion skill directory
is correct so the skill sync step works.
"""

from __future__ import annotations

from pathlib import Path

from cli._harness.base import GrantResult, HarnessAdapter


class CodexAdapter(HarnessAdapter):
    """Codex agent harness.

    Companion install is supported (sync into ``~/.codex/skills``);
    autopost grant is a no-op because Codex has no per-command
    permission list.
    """

    name = "codex"
    display_name = "Codex"

    def __init__(
        self,
        *,
        project_dir: Path | None = None,  # noqa: ARG002
        home_dir: Path | None = None,
    ) -> None:
        self._home_dir = home_dir

    def _home(self) -> Path:
        return self._home_dir if self._home_dir is not None else Path.home()

    def skill_dir(self) -> Path:
        return self._home() / ".codex" / "skills"

    def is_present(self) -> bool:
        import shutil

        return (self._home() / ".codex").is_dir() or (
            shutil.which("codex") is not None
        )

    def config_path(self, scope: str) -> Path:  # noqa: ARG002
        return self._home() / ".codex" / "config.toml"

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

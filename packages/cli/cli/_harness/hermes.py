# SPDX-License-Identifier: MIT
"""Hermes Agent harness adapter.

Hermes stores its configuration in ``~/.hermes/config.yaml`` (YAML, not
JSON) and loads skills from ``~/.hermes/skills/``.  Permission gating
in Hermes is controlled by ``approvals.mode`` in config.yaml (``manual``,
``smart``, or ``off``) — there is no per-command allow list like Claude
Code's ``permissions.allow``.  The ``--yolo`` flag bypasses all approval
prompts globally, but Logion cannot pre-authorise a single command.

Therefore the autopost grant is a **no-op** for Hermes: ``grant`` and
``revoke`` report ``already=True`` without writing anything, and
``is_granted`` always returns ``False`` (the permission model does not
support per-command grants).  The companion skill directory is still
correct so the symlink step works.
"""

from __future__ import annotations

from pathlib import Path

from cli._harness.base import GrantResult, HarnessAdapter


class HermesAdapter(HarnessAdapter):
    """Hermes agent harness.

    Companion install is supported (symlink into ``~/.hermes/skills``);
    autopost grant is a no-op because Hermes has no per-command
    permission list.
    """

    name = "hermes"
    display_name = "Hermes"

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
        return self._home() / ".hermes" / "skills"

    def is_present(self) -> bool:
        import shutil

        return (self._home() / ".hermes").is_dir() or (
            shutil.which("hermes") is not None
        )

    def config_path(self, scope: str) -> Path:  # noqa: ARG002
        return self._home() / ".hermes" / "config.yaml"

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

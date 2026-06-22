# SPDX-License-Identifier: MIT
"""Hermes Agent harness adapter.

Hermes stores its configuration in ``~/.hermes/config.yaml`` (YAML, not
JSON) and loads skills from ``~/.hermes/skills/``.  Permission gating is
controlled by ``approvals.mode`` (``manual`` / ``smart`` / ``off``), and
Hermes *does* keep a per-command allow list — ``command_allowlist`` in
config.yaml — that bypasses approval in future sessions:

    command_allowlist:
      - rm
      - systemctl

Crucially, those entries are keyed on the **command name** (approving
``rm -rf`` "always" stores ``rm``), not a full command line.  Logion's
autopost grant is deliberately sub-command-scoped — *exactly*
``logion courses report-usage``, nothing broader (see ``base.py``).
That scope is not expressible in ``command_allowlist``: the only entry
we could add is ``logion``, which would pre-approve **every** ``logion``
command.  Over-granting like that defeats the point of the grant.

Therefore the autopost grant is a **no-op** for Hermes: ``grant`` and
``revoke`` report ``already=True`` without writing anything, and
``is_granted`` always returns ``False`` — not because Hermes lacks an
allow list, but because its allow list cannot express a least-privilege,
sub-command-scoped grant.  The companion skill directory is still
correct so the symlink step works.  (``--yolo`` / ``HERMES_YOLO_MODE``
exist but bypass *all* approvals globally — never something Logion sets.)
"""

from __future__ import annotations

from pathlib import Path

from cli._harness.base import GrantResult, HarnessAdapter


class HermesAdapter(HarnessAdapter):
    """Hermes agent harness.

    Companion install is supported (symlink into ``~/.hermes/skills``);
    autopost grant is a no-op because Hermes's ``command_allowlist`` is
    keyed on command name and cannot express a sub-command-scoped grant
    without over-granting all ``logion`` commands (see module docstring).
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

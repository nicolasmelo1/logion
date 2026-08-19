# SPDX-License-Identifier: MIT
"""Hermes Agent harness adapter.

Hermes stores its configuration in ``~/.hermes/config.yaml`` (YAML, not
JSON) and loads skills from ``~/.hermes/skills/``.  Permission gating is
controlled by ``approvals.mode`` (``manual`` / ``smart`` / ``off``), and
Hermes *does* keep a per-command allow list — ``command_allowlist`` in
config.yaml — but it is keyed on command name, so a sub-command-scoped
grant cannot be expressed without over-granting all ``logion`` commands.

Therefore the autopost grant is a **no-op** for Hermes.

Use observation is a different story, and an earlier revision of this
adapter got it wrong.  Hermes documents a Python plugin system with
lifecycle hooks — see
<https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins>.
Plugins expose ``register(ctx)`` in ``__init__.py``, are discovered from
``~/.hermes/plugins/``, ``./.hermes/plugins/``, bundled sources and pip
entry-points, and are gated by the ``plugins.enabled`` allow-list in
``~/.hermes/config.yaml``.  Hooks are attached with
``ctx.register_hook(name, callback)``.

Two of the documented observer hooks are exactly what use observation
needs, and one of them is better than anything Claude Code offers:

- ``on_skill_lifecycle`` — a *named* skill lifecycle event.  Claude Code
  has no equivalent; there, skill use has to be inferred from
  ``PostToolUse``.
- ``post_tool_call`` — tool-use observation.

``on_session_start`` / ``on_session_end`` are also available and are what
the session-scoped dedup window and the end-of-session pending prompt
would bind to.

What is *not* yet known is the payload shape each hook delivers.  Phase
15.11 is explicit that an adapter counts as supported only after a
recorded real-harness fixture, and that the implementer must verify the
hook schema against official documentation rather than trust the plan.
The hook names above come from that documentation; the field mapping does
not exist yet, and guessing it would violate the standing rule that
ambiguous attribution is dropped rather than inferred.

So this adapter reports :data:`~cli._harness.base.HOOK_NOT_PINNED`: the
surface exists, the fixture does not.  It deliberately does **not** report
``EXPLICIT_REPORT``, which would set ``supported=True, already=True`` and
tell a Hermes user that their harness is already covered.

Scope targets :

- ``user`` → ``$HOME/.hermes/skills`` (active profile home).
- ``repo-root`` → ``$REPO_ROOT/.agents/skills`` (shared target,
  registered as an external directory for the isolated Hermes profile).
- Other repo scopes resolve to ``.agents/skills`` under the matching
  directory.
"""

from __future__ import annotations

import os
from pathlib import Path

from cli._harness.base import (
    GrantResult,
    HarnessAdapter,
    ObservationPlan,
)
from cli._harness.scopes import (
    REPO_CURRENT,
    REPO_PARENT,
    REPO_ROOT,
    USER,
    ScopeTarget,
    canonical_scope,
)

#: Package name a Logion observer plugin would take inside
#: ``~/.hermes/plugins/``.  Fixed so that detection, install and uninstall
#: all match on the same directory.
OBSERVER_PLUGIN_NAME = "logion-observer"


def _git_root(cwd: Path) -> Path | None:
    """Walk up from *cwd* looking for a ``.git`` dir/file."""
    path = Path(cwd).resolve()
    while True:
        if (path / ".git").exists():
            return path
        if path.parent == path:
            return None
        path = path.parent


class HermesAdapter(HarnessAdapter):
    """Hermes agent harness.

    User skills resolve to ``$HOME/.hermes/skills`` (the active
    profile's skill directory).  Repository-scope installs use the
    shared ``.agents/skills`` target and are registered as Hermes
    external directories.  Autopost grant is a no-op.
    """

    name = "hermes"
    display_name = "Hermes"

    def __init__(
        self,
        *,
        project_dir: Path | None = None,
        home_dir: Path | None = None,
        cwd: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._project_dir = project_dir
        self._home_dir = home_dir
        self._cwd = cwd
        self._repo_root = repo_root

    def _home(self) -> Path:
        return self._home_dir if self._home_dir is not None else Path.home()

    def _hermes_home(self) -> Path:
        configured = os.environ.get("HERMES_HOME")
        if configured:
            return Path(configured).expanduser()
        return self._home() / ".hermes"

    def _cwd_path(self) -> Path:
        if self._cwd is not None:
            return Path(self._cwd)
        if self._project_dir is not None:
            return Path(self._project_dir)
        return Path.cwd()

    def _repo_root_path(self) -> Path | None:
        if self._repo_root is not None:
            return Path(self._repo_root)
        return _git_root(self._cwd_path())

    # -- scope targets -----------------------------------------------------

    def scope_targets(self, scope: str) -> list[ScopeTarget]:
        cscope = canonical_scope(scope)
        cwd = self._cwd_path()
        repo_root = self._repo_root_path()

        if cscope == USER:
            hermes_home = self._hermes_home()
            target = hermes_home / "skills"
            return [
                ScopeTarget(
                    USER,
                    hermes_home,
                    target,
                    "hermes",
                    target.exists(),
                )
            ]
        if cscope == REPO_ROOT:
            if repo_root is None:
                return []
            # Shared cross-harness target; Hermes registers it as an
            # external directory for the isolated profile.
            target = repo_root / ".agents" / "skills"
            return [
                ScopeTarget(
                    REPO_ROOT, repo_root, target, None, target.exists()
                )
            ]
        if cscope == REPO_CURRENT:
            target = cwd / ".agents" / "skills"
            return [
                ScopeTarget(REPO_CURRENT, cwd, target, None, target.exists())
            ]
        if cscope == REPO_PARENT:
            if repo_root is None:
                return []
            parent = cwd.parent
            if parent == repo_root or not self._is_inside(cwd, repo_root):
                return []
            target = parent / ".agents" / "skills"
            return [
                ScopeTarget(REPO_PARENT, parent, target, None, target.exists())
            ]
        # admin/system/custom unsupported by Hermes.
        return []

    @staticmethod
    def _is_inside(child: Path, root: Path) -> bool:
        try:
            child.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return True

    def skill_dir(self) -> Path:
        targets = self.scope_targets(USER)
        return targets[0].target_path

    def is_present(self) -> bool:
        import shutil

        return (
            self._hermes_home().is_dir() or shutil.which("hermes") is not None
        )

    def config_path(self, scope: str) -> Path:  # noqa: ARG002
        return self._hermes_home() / "config.yaml"

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

    # -- use observation ---------------------------------------------------

    #: Observer hooks this adapter will bind once their payloads are pinned.
    #: ``on_skill_lifecycle`` is the one worth the wait: it names skill
    #: activation directly instead of leaving it to be inferred.
    OBSERVER_HOOKS: tuple[str, ...] = (
        "on_skill_lifecycle",
        "post_tool_call",
    )

    #: Allow-list key in ``config.yaml`` that gates a general plugin.
    PLUGIN_ENABLE_KEY: tuple[str, ...] = ("plugins", "enabled")

    def plugin_dir(self, scope: str) -> Path | None:
        """Where a Logion observer plugin would be installed for *scope*.

        Mirrors :meth:`scope_targets`: the user scope lives under the
        Hermes home, repository scopes under a project-local ``.hermes``.
        ``None`` for scopes Hermes does not express, so a caller never
        renders a path that could not exist.
        """
        cscope = canonical_scope(scope)
        if cscope == USER:
            return self._hermes_home() / "plugins" / OBSERVER_PLUGIN_NAME
        targets = self.scope_targets(cscope)
        if not targets:
            return None
        return (
            targets[0].scope_root
            / ".hermes"
            / "plugins"
            / OBSERVER_PLUGIN_NAME
        )

    def observation_config_path(self, scope: str) -> Path | None:  # noqa: ARG002
        """``None``: there is nothing Logion can write here yet.

        ``integrations detect`` derives ``observation_supported`` from this
        method, so returning :meth:`plugin_dir` would advertise Hermes as
        supported — the same overclaim this adapter exists to remove, moved
        into a different field. The path is not lost: :meth:`plugin_dir`
        keeps it, and the observation plan carries it so a user can see
        where the work lands.
        """
        return None

    def plan_observation(self, scope: str) -> ObservationPlan:
        return self._hook_not_pinned(scope, path=self.plugin_dir(scope))

    def enable_observation(self, scope: str) -> ObservationPlan:
        return self._hook_not_pinned(scope, path=self.plugin_dir(scope))

    def disable_observation(self, scope: str) -> ObservationPlan:
        return self._hook_not_pinned(scope, path=self.plugin_dir(scope))

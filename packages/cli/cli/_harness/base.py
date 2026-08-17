# SPDX-License-Identifier: MIT
"""Harness adapter contract.

A *harness* is whatever agent runtime the user drives Logion from —
Claude Code, Codex, OpenCode, Amp, and so on.  Each one gates (or does
not gate) the commands an agent may run, and each expresses those
permissions in its own config format.

Logion cannot pre-authorize an outward-facing command across every
harness from one place — that protection belongs to each tool's
operator.  What Logion *can* do is translate a single, well-scoped
grant ("let the agent run ``logion courses report-usage`` without
prompting") into whatever native config the harness on this machine
understands.

Each harness gets one :class:`HarnessAdapter`.  Supporting a new harness
is a new adapter added to the registry in ``__init__.py`` — no caller
changes.  The grant itself is defined once, here, as
:data:`AUTOPOST_COMMAND`; adapters render it into their own syntax.

adds :meth:`scope_targets`, the semantic scope vocabulary
defined in :mod:`cli._harness.scopes`.  Adapters declare the native
locations they scan for each scope so that ``resources acquire`` and
``resources inventory`` can resolve targets without per-harness
hard-coding in the command layer.
"""

from __future__ import annotations

import difflib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from cli._harness.scopes import (
    USER,
    ScopeTarget,
    canonical_scope,
)
from cli._harness.scopes import (
    VALID_SCOPES as SCOPE_VOCABULARY,
)
from cli._json import JsonObject

# The command whose autonomous execution the autopost grant authorizes.
# Defined once; each adapter renders it into its harness's permission
# syntax (e.g. Claude Code's ``Bash(logion courses report-usage:*)``).
AUTOPOST_COMMAND: tuple[str, ...] = ("logion", "courses", "report-usage")

# The command a harness hook invokes to report one use event. Adapters
# render it into their own hook syntax; the prefix is also what uninstall
# matches on, so it must stay stable.
OBSERVATION_COMMAND: tuple[str, ...] = ("logion", "usage", "observe")

# Typed result for a harness that exposes no trustworthy local tool-use
# event. Reported as-is rather than inferring use from installation.
INVENTORY_ONLY = "inventory_only_observation_unsupported"

# Permission scopes an adapter must understand. Kept as the canonical
# semantic vocabulary from :mod:`cli._harness.scopes`; aliases
# (``project``, ``global``) are accepted on input via
# :func:`cli._harness.scopes.canonical_scope`.
VALID_SCOPES: frozenset[str] = SCOPE_VOCABULARY


class HarnessConfigError(RuntimeError):
    """Raised when a harness config exists but cannot be safely edited.

    Surfaced (never swallowed) so the caller refuses to clobber a config
    file it could not parse, rather than overwriting the user's settings.
    """


@dataclass(frozen=True)
class GrantResult:
    """Outcome of a grant/revoke on one harness at one scope."""

    harness: str  # adapter ``name`` (e.g. "claude-code")
    scope: str  # canonical scope (e.g. "repo-root" or "user")
    path: Path  # config file inspected/edited
    changed: bool  # True if the file was actually written
    already: bool  # grant: rule was already present; revoke: already absent

    def to_dict(self) -> JsonObject:
        """JSON-safe view for ``--json`` output."""
        return {
            "harness": self.harness,
            "scope": self.scope,
            "path": str(self.path),
            "changed": self.changed,
            "already": self.already,
        }


@dataclass(frozen=True)
class ObservationPlan:
    """What enabling/disabling observation on one harness would do.

    Carries the rendered config diff so ``--dry-run`` can show the exact
    edit before the user consents to it.
    """

    harness: str
    scope: str
    supported: bool
    path: Path | None
    already: bool
    changed: bool
    before: str = ""
    after: str = ""
    reason: str | None = None

    @property
    def diff(self) -> str:
        """Unified diff of the config file this plan would write."""
        if self.path is None or self.before == self.after:
            return ""
        name = str(self.path)
        return "".join(
            difflib.unified_diff(
                self.before.splitlines(keepends=True),
                self.after.splitlines(keepends=True),
                fromfile=f"a/{name}",
                tofile=f"b/{name}",
            )
        )

    def to_dict(self) -> JsonObject:
        """JSON-safe view for ``--json`` output."""
        return {
            "harness": self.harness,
            "scope": self.scope,
            "supported": self.supported,
            "path": str(self.path) if self.path is not None else None,
            "already": self.already,
            "changed": self.changed,
            "diff": self.diff,
            "reason": self.reason,
        }


class HarnessAdapter(ABC):
    """Bridges the Logion autopost grant to one harness's permission model.

    Subclasses also declare :meth:`scope_targets` so the resource
    acquire/inventory commands can resolve native installation locations
    per scope without hard-coding harness layout in the command layer.
    """

    #: Stable machine id, used by ``--harness`` (e.g. "claude-code").
    name: str = "unnamed"
    #: Human-facing label (e.g. "Claude Code").
    display_name: str = "Unnamed harness"

    @abstractmethod
    def is_present(self) -> bool:
        """True if this harness appears installed/configured for the user."""
        ...

    @abstractmethod
    def config_path(self, scope: str) -> Path:
        """Resolve the settings file for *scope* (canonical or aliased)."""
        ...

    @abstractmethod
    def is_granted(self, scope: str) -> bool:
        """True if the autopost grant is already present at *scope*."""
        ...

    @abstractmethod
    def grant(self, scope: str) -> GrantResult:
        """Add the autopost permission at *scope*.  Idempotent."""
        ...

    @abstractmethod
    def revoke(self, scope: str) -> GrantResult:
        """Remove the autopost permission at *scope*.  Idempotent."""
        ...

    @abstractmethod
    def scope_targets(self, scope: str) -> list[ScopeTarget]:
        """Resolved native targets for *scope*.

        Returns one or more :class:`ScopeTarget` entries describing the
        concrete directories this harness scans for the given scope.
        ``system`` returns inventory-only targets (no install path).
        Adapters return an empty list for scopes they do not support
        rather than raising — callers treat empty as "unsupported".
        """
        ...

    # -- use observation ---------------------------------------------------

    def observation_command(self) -> str:
        """The hook command line that reports one use event to Logion."""
        return f"{' '.join(OBSERVATION_COMMAND)} --harness {self.name} --stdin"

    def observation_config_path(self, scope: str) -> Path | None:  # noqa: ARG002
        """Config file that would carry the hook, or ``None`` if unsupported.

        The base implementation returns ``None``: a harness supports use
        observation only once an adapter has been written against its
        documented hook schema and a recorded payload fixture.
        """
        return None

    def plan_observation(self, scope: str) -> ObservationPlan:
        """Describe enabling observation without writing anything."""
        return self._unsupported(scope)

    def enable_observation(self, scope: str) -> ObservationPlan:
        """Install the observation hook at *scope*.  Idempotent."""
        return self._unsupported(scope)

    def disable_observation(self, scope: str) -> ObservationPlan:
        """Remove the Logion-owned observation hook.  Idempotent."""
        return self._unsupported(scope)

    def _unsupported(self, scope: str) -> ObservationPlan:
        return ObservationPlan(
            harness=self.name,
            scope=canonical_scope(scope),
            supported=False,
            path=None,
            already=False,
            changed=False,
            reason=INVENTORY_ONLY,
        )

    def skill_dir(self) -> Path:
        """Absolute dir this harness loads user skills from.

        Compatibility wrapper: delegates to the first ``user`` scope
        target path.  Legacy callers (onboarding, symlink) continue to
        work; new code should use :meth:`scope_targets` directly.
        """
        targets = self.scope_targets(USER)
        if not targets:
            raise NotImplementedError(
                f"{self.name} does not declare a user scope target"
            )
        return targets[0].target_path


def _canonical(scope: str) -> str:
    """Public re-export of :func:`cli._harness.scopes.canonical_scope`."""
    return canonical_scope(scope)


__all__ = [
    "AUTOPOST_COMMAND",
    "INVENTORY_ONLY",
    "OBSERVATION_COMMAND",
    "VALID_SCOPES",
    "GrantResult",
    "HarnessAdapter",
    "HarnessConfigError",
    "ObservationPlan",
    "ScopeTarget",
]

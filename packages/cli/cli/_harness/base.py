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
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

# The command whose autonomous execution the autopost grant authorizes.
# Defined once; each adapter renders it into its harness's permission
# syntax (e.g. Claude Code's ``Bash(logion courses report-usage:*)``).
AUTOPOST_COMMAND: tuple[str, ...] = ("logion", "courses", "report-usage")

# Permission scopes an adapter must understand.
VALID_SCOPES: frozenset[str] = frozenset({"project", "global"})


class HarnessConfigError(RuntimeError):
    """Raised when a harness config exists but cannot be safely edited.

    Surfaced (never swallowed) so the caller refuses to clobber a config
    file it could not parse, rather than overwriting the user's settings.
    """


@dataclass(frozen=True)
class GrantResult:
    """Outcome of a grant/revoke on one harness at one scope."""

    harness: str  # adapter ``name`` (e.g. "claude-code")
    scope: str  # "project" | "global"
    path: Path  # config file inspected/edited
    changed: bool  # True if the file was actually written
    already: bool  # grant: rule was already present; revoke: already absent

    def to_dict(self) -> dict[str, object]:
        """JSON-safe view for ``--json`` output."""
        return {
            "harness": self.harness,
            "scope": self.scope,
            "path": str(self.path),
            "changed": self.changed,
            "already": self.already,
        }


class HarnessAdapter(ABC):
    """Bridges the Logion autopost grant to one harness's permission model."""

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
        """Resolve the settings file for *scope* ("project" | "global")."""
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

# SPDX-License-Identifier: MIT
"""Semantic scope vocabulary for harness resource installation.

Logion installs resources (skills, plugins, MCP servers, ...) into a
harness's native locations.  The *scope* selects which location.  This
module defines the canonical scope names, compatibility aliases, and
resolution helpers shared by every adapter.

Semantic scopes (never aliased away):

- ``repo-current`` — current working directory.
- ``repo-parent`` — an explicitly selected parent between CWD and root.
- ``repo-root`` — the detected topmost Git repository root.
- ``user`` — the harness's per-user location.
- ``admin`` — a machine/container administrator location.
- ``system`` — harness-bundled; read-only inventory, never installed.
- ``custom`` — explicit user path with no inferred semantics.

``project`` remains a compatibility alias for ``repo-root`` and ``global``
for ``user`` until callers migrate.  New code stores the semantic value.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# --- semantic scope constants ---------------------------------------------

REPO_CURRENT = "repo-current"
REPO_PARENT = "repo-parent"
REPO_ROOT = "repo-root"
USER = "user"
ADMIN = "admin"
SYSTEM = "system"
CUSTOM = "custom"

# --- compatibility aliases ------------------------------------------------
# ``project`` and ``global`` are accepted on input but canonicalised to
# their semantic equivalents before any storage or comparison.

PROJECT = "project"  # alias for repo-root
GLOBAL = "global"  # alias for user

VALID_SCOPES: frozenset[str] = frozenset({
    REPO_CURRENT,
    REPO_PARENT,
    REPO_ROOT,
    USER,
    ADMIN,
    SYSTEM,
    CUSTOM,
})

ALIASES: dict[str, str] = {
    PROJECT: REPO_ROOT,
    GLOBAL: USER,
}


def canonical_scope(scope: str) -> str:
    """Resolve *scope* to its canonical semantic value.

    Aliases (``project``, ``global``) are mapped to ``repo-root`` and
    ``user`` respectively.  Semantic scopes pass through unchanged.
    """
    return ALIASES.get(scope, scope)


def is_valid_scope(scope: str) -> bool:
    """True if *scope* (or its alias) is a recognised scope."""
    return canonical_scope(scope) in VALID_SCOPES


def _git_root(cwd: Path) -> Path | None:
    """Walk up from *cwd* looking for a ``.git`` dir/file.

    Returns the repository root or ``None`` if not inside a Git repo.
    """
    path = cwd.resolve()
    while True:
        if (path / ".git").exists():
            return path
        if path.parent == path:
            return None
        path = path.parent


def default_scope_for_cwd(cwd: Path) -> str:
    """Return the default scope for a process launched in *cwd*.

    Inside a Git repository the default is ``repo-root``. Outside a
    repository the default is ``user``; callers must surface the resulting
    cross-scope confirmation before a future write is allowed.
    """
    if _git_root(Path(cwd)) is not None:
        return REPO_ROOT
    return USER


@dataclass(frozen=True)
class ScopeTarget:
    """One resolved installation target for a scope.

    - ``scope_kind`` — canonical scope (e.g. ``repo-root``).
    - ``scope_root`` — the root directory anchoring this target
      (repo root, home, ``/etc``, ...).
    - ``target_path`` — the concrete skills directory the harness scans.
    - ``native_manager`` — the harness's native tool that manages this
      location (e.g. ``"codex skills"``), or ``None`` when Logion copies
      directly.
    - ``exists`` — whether ``target_path`` currently exists on disk.
    """

    scope_kind: str
    scope_root: Path
    target_path: Path
    native_manager: str | None
    exists: bool


__all__ = [
    "ADMIN",
    "ALIASES",
    "CUSTOM",
    "GLOBAL",
    "PROJECT",
    "REPO_CURRENT",
    "REPO_PARENT",
    "REPO_ROOT",
    "SYSTEM",
    "USER",
    "VALID_SCOPES",
    "ScopeTarget",
    "canonical_scope",
    "default_scope_for_cwd",
    "is_valid_scope",
]

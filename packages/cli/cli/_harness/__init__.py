# SPDX-License-Identifier: MIT
"""Harness adapter registry.

To support a new agent harness (Codex, OpenCode, Amp, Pi, ...), implement a
:class:`~cli._harness.base.HarnessAdapter` and add it to
:data:`_ADAPTER_TYPES`.  Nothing else changes — the onboarding flow and
``--harness`` selection discover adapters through this registry.
"""

from __future__ import annotations

from cli._harness.base import (
    AUTOPOST_COMMAND,
    GrantResult,
    HarnessAdapter,
    HarnessConfigError,
    ScopeTarget,
)
from cli._harness.claude_code import ClaudeCodeAdapter
from cli._harness.codex import CodexAdapter
from cli._harness.dsh import DshAdapter
from cli._harness.hermes import HermesAdapter
from cli._harness.opencode import OpenCodeAdapter
from cli._harness.pi import PiAdapter
from cli._harness.scopes import (
    VALID_SCOPES,
    canonical_scope,
    default_scope_for_cwd,
    is_valid_scope,
)

# Ordered registry of known adapter types.  Append new harnesses here.
_ADAPTER_TYPES: tuple[type[HarnessAdapter], ...] = (
    ClaudeCodeAdapter,
    CodexAdapter,
    OpenCodeAdapter,
    HermesAdapter,
    PiAdapter,
    DshAdapter,
)


def all_adapters() -> list[HarnessAdapter]:
    """Instantiate every registered adapter (production defaults)."""
    return [cls() for cls in _ADAPTER_TYPES]


def adapter_names() -> list[str]:
    """Return the stable names of all registered harnesses."""
    return [a.name for a in all_adapters()]


def get_adapter(name: str) -> HarnessAdapter | None:
    """Return the adapter with *name*, or ``None`` if unknown."""
    for adapter in all_adapters():
        if adapter.name == name:
            return adapter
    return None


def detect_present() -> list[HarnessAdapter]:
    """Return adapters whose harness appears installed on this machine."""
    return [a for a in all_adapters() if a.is_present()]


__all__ = [
    "AUTOPOST_COMMAND",
    "VALID_SCOPES",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "DshAdapter",
    "GrantResult",
    "HarnessAdapter",
    "HarnessConfigError",
    "HermesAdapter",
    "OpenCodeAdapter",
    "PiAdapter",
    "ScopeTarget",
    "adapter_names",
    "all_adapters",
    "canonical_scope",
    "default_scope_for_cwd",
    "detect_present",
    "get_adapter",
    "is_valid_scope",
]

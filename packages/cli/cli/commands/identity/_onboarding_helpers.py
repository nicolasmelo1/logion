# SPDX-License-Identifier: MIT
"""Orchestration helpers for ``identity onboarding``.

Extracted from ``onboarding.py`` to keep that module under the CLI's
per-file source-size budget (250 lines).  These functions coordinate
the companion and harness-validation steps; they are not part of the
``_companion`` module because they are onboarding-flow glue, not
companion-install primitives.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cli._errors import print_err
from cli._harness import detect_present, get_adapter
from cli._harness.base import HarnessAdapter

from ._companion import (
    CompanionInstallError,
    CompanionNotFoundError,
    CompanionResult,
    install_companion,
)


def empty_companion_summary() -> dict[str, object]:
    return {
        "installed": False,
        "skill_dir": None,
        "course_id": None,
        "version_id": None,
        "already": False,
    }


def validate_explicit_harness(args: argparse.Namespace) -> int | None:
    """Return an exit code if an explicit ``--harness`` is invalid."""
    from cli._harness import get_adapter

    requested = getattr(args, "harness", None)
    if (
        requested
        and not getattr(args, "agent_dir", None)
        and get_adapter(requested) is None
    ):
        print_err(f"Error: unknown harness '{requested}'.")
        return 2
    return None


def run_companion_step(
    args: argparse.Namespace,
) -> tuple[dict[str, object], int | None]:
    """Run the companion install step.

    Returns ``(summary_dict, exit_code_or_none)``.  A non-None exit
    code means the caller should return it immediately.
    """
    if getattr(args, "no_companion", False):
        return empty_companion_summary(), None

    try:
        adapter = resolve_target_adapter(args)
    except CompanionNotFoundError:
        return empty_companion_summary(), 2

    if adapter is None:
        print_err(
            "No supported agent harness detected, so the companion "
            "bundle was not installed. Re-run with --harness <name> "
            "or --agent-dir <path>."
        )
        return empty_companion_summary(), None

    try:
        companion = install_companion(args, adapter)
    except CompanionNotFoundError as exc:
        print_err(f"Warning: companion not installed: {exc}")
        companion = CompanionResult(
            installed=False,
            skill_dir=None,
            course_id=None,
            version_id=None,
            already=False,
        )
    except CompanionInstallError as exc:
        print_err(f"Error: companion install failed: {exc}")
        return empty_companion_summary(), 2
    return companion.to_dict(), None


def ensure_symlink(adapter: HarnessAdapter, install_dest: Path) -> None:
    """Symlink ``install_dest`` into ``adapter.skill_dir()``.

    Uses the existing ``create_symlink`` helper so we share the same
    replace-prior-link/refuse-real-directory behaviour as
    ``logion skills install --symlink-dir``.
    """
    from cli.commands.skills._agent_symlink import create_symlink

    skill_name = "logion-marketplace-companion"
    target_skill_dir = adapter.skill_dir()
    create_symlink(target_skill_dir, skill_name, install_dest)


def resolve_target_adapter(
    args: argparse.Namespace,
) -> HarnessAdapter | None:
    """Resolve the adapter for the companion step.

    Returns ``None`` only when no harness is auto-detected and neither
    ``--harness`` nor ``--agent-dir`` was given.  An explicit but
    unknown ``--harness`` is a hard error (raised below), not a silent
    skip.
    """
    from cli._harness.custom import CustomPathHarness

    agent_dir = getattr(args, "agent_dir", None)
    if agent_dir:
        return CustomPathHarness(Path(agent_dir).expanduser())

    harness = getattr(args, "harness", None)
    if harness:
        adapter = get_adapter(harness)
        if adapter is None:
            print_err(f"Error: unknown harness '{harness}'.")
            raise CompanionNotFoundError(f"unknown harness: {harness}")
        return adapter

    present = detect_present()
    return present[0] if present else None

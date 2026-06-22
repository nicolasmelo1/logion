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

from cli._errors import print_err

from ._companion import (
    CompanionInstallError,
    CompanionNotFoundError,
    CompanionResult,
    install_companion,
    resolve_target_adapter,
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

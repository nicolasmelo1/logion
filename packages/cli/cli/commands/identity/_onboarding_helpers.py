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
from cli._harness import adapter_names, detect_present, get_adapter
from cli._harness.base import HarnessAdapter

from ._companion import (
    COMPANION_COURSE_ID,
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
    requested = getattr(args, "harness", None)
    if (
        requested
        and not getattr(args, "agent_dir", None)
        and get_adapter(requested) is None
    ):
        print_err(
            f"Error: unknown harness '{requested}'. "
            f"Supported: {', '.join(adapter_names())}."
        )
        return 2
    return None


def run_companion_step(
    args: argparse.Namespace,
) -> tuple[dict[str, object], int | None]:
    """Run the companion install step.

    Returns ``(summary_dict, exit_code_or_none)``.  A non-None exit
    code means the caller should return it immediately.

    When multiple harnesses are auto-detected, the companion is
    installed into **every** detected harness, matching autopost's
    behaviour of granting across all present harnesses.  An explicit
    ``--harness`` or ``--agent-dir`` restricts the target to one.
    """
    if getattr(args, "no_companion", False):
        return empty_companion_summary(), None

    try:
        adapters = resolve_target_adapters(args)
    except CompanionNotFoundError:
        return empty_companion_summary(), 2

    if not adapters:
        print_err(
            "No supported agent harness detected, so the companion "
            "bundle was not installed. Re-run with --harness <name> "
            "or --agent-dir <path>."
        )
        return empty_companion_summary(), None

    # Install the companion into each resolved adapter.  The canonical
    # install (manifest + content hash) happens once per (course_id,
    # version_id); subsequent adapters just get a symlink.
    summaries: list[dict[str, object]] = []
    for adapter in adapters:
        try:
            companion = install_companion(args, adapter)
        except CompanionNotFoundError as exc:
            print_err(
                f"Warning: companion not installed for {adapter.name}: {exc}"
            )
            companion = CompanionResult(
                installed=False,
                skill_dir=None,
                course_id=None,
                version_id=None,
                already=False,
            )
        except CompanionInstallError as exc:
            print_err(
                f"Error: companion install failed for {adapter.name}: {exc}"
            )
            return empty_companion_summary(), 2
        summaries.append(companion.to_dict())

    # The JSON summary mirrors the single-harness shape for backwards
    # compatibility: the first adapter's result, with a ``harnesses``
    # list when more than one was targeted.
    result = dict(summaries[0])
    if len(summaries) > 1:
        result["harnesses"] = summaries
    return result, None


def ensure_symlink(adapter: HarnessAdapter, install_dest: Path) -> None:
    """Symlink ``install_dest`` into ``adapter.skill_dir()``.

    Uses the existing ``create_symlink`` helper so we share the same
    replace-prior-link/refuse-real-directory behaviour as
    ``logion skills install --symlink-dir``.
    """
    from cli.commands.skills._agent_symlink import create_symlink

    skill_name = COMPANION_COURSE_ID
    target_skill_dir = adapter.skill_dir()
    create_symlink(target_skill_dir, skill_name, install_dest)


def resolve_target_adapters(
    args: argparse.Namespace,
) -> list[HarnessAdapter]:
    """Resolve the adapter(s) for the companion step.

    Returns a list (possibly empty).  An explicit but unknown
    ``--harness`` is a hard error (raised below), not a silent skip.

    When no explicit harness or agent-dir is given, auto-detected
    harnesses are returned as a list — the companion is installed
    into all of them, matching autopost's multi-harness behaviour.
    """
    from cli._harness.custom import CustomPathHarness

    agent_dir = getattr(args, "agent_dir", None)
    if agent_dir:
        return [CustomPathHarness(Path(agent_dir).expanduser())]

    harness = getattr(args, "harness", None)
    if harness:
        adapter = get_adapter(harness)
        if adapter is None:
            # Message already printed by validate_explicit_harness.
            raise CompanionNotFoundError(f"unknown harness: {harness}")
        return [adapter]

    return detect_present()

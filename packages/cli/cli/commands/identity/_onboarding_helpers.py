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
from cli._harness import adapter_names, get_adapter
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
    """Return an exit code if any explicit ``--harness`` is invalid.

    ``--harness`` is repeatable, so every requested name is validated.
    Validated whenever ``--harness`` is set, *regardless of*
    ``--agent-dir``: ``--agent-dir`` only overrides the companion
    target, but ``--harness`` still drives the autopost grant and the
    harness selection.
    """
    requested = getattr(args, "harness", None) or []
    for name in requested:
        if get_adapter(name) is None:
            print_err(
                f"Error: unknown harness '{name}'. "
                f"Supported: {', '.join(adapter_names())}."
            )
            return 2
    return None


def run_companion_step(
    args: argparse.Namespace,
    adapters: list[HarnessAdapter],
) -> tuple[dict[str, object], int | None]:
    """Run the companion install step.

    Returns ``(summary_dict, exit_code_or_none)``.  A non-None exit
    code means the caller should return it immediately.

    *adapters* is the harness selection resolved once by
    ``select_harnesses``; the companion is installed into each. An
    explicit ``--agent-dir`` overrides the target to that single skill
    dir (a ``CustomPathHarness``), independent of the selection.
    """
    if getattr(args, "no_companion", False):
        return empty_companion_summary(), None

    targets = companion_targets(args, adapters)

    if not targets:
        print_err(
            "No agent harness selected, so the companion bundle was not "
            "installed. Re-run with --harness <name> or --agent-dir <path>."
        )
        return empty_companion_summary(), None
    adapters = targets

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


def ensure_symlink(
    adapter: HarnessAdapter,
    install_dest: Path,
    skill_name: str | None = None,
) -> None:
    """Symlink ``install_dest`` into ``adapter.skill_dir()``.

    Uses the existing ``create_symlink`` helper so we share the same
    replace-prior-link/refuse-real-directory behaviour as
    ``logion skills install --symlink-dir``.

    A symlink failure is **non-fatal and never raises**: it is surfaced
    as a warning on stderr (mirroring ``apply_post_install_symlink``),
    so onboarding does not crash — or corrupt ``--json`` with a
    traceback — when the target is a real directory or otherwise
    unwritable.  The canonical install under ``$LOGION_HOME/installed/``
    is valid regardless.
    """
    from cli.commands.skills._agent_symlink import create_symlink

    skill_name = skill_name or COMPANION_COURSE_ID
    target_skill_dir = adapter.skill_dir()
    try:
        create_symlink(target_skill_dir, skill_name, install_dest)
    except FileExistsError as exc:
        print_err(f"Warning: companion symlink skipped: {exc}")
    except OSError as exc:
        print_err(
            f"Warning: companion symlink failed ({exc}); "
            "canonical install is fine."
        )


def companion_targets(
    args: argparse.Namespace,
    adapters: list[HarnessAdapter],
) -> list[HarnessAdapter]:
    """Resolve the adapter(s) for the companion step.

    ``--agent-dir`` overrides the resolved selection with a single
    ``CustomPathHarness``; otherwise the shared *adapters* selection is
    used as-is.
    """
    agent_dir = getattr(args, "agent_dir", None)
    if agent_dir:
        from cli._harness.custom import CustomPathHarness

        return [CustomPathHarness(Path(agent_dir).expanduser())]
    return adapters

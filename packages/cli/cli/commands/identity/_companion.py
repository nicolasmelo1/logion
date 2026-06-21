# SPDX-License-Identifier: MIT
"""Companion-bundle step for ``identity onboarding``.

Locates the companion bundle directory and symlinks it into the
chosen harness's ``skill_dir``.  The canonical install is delegated to
the existing ``logion skills install --source <dir>`` path.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from cli._harness import detect_present, get_adapter
from cli._harness.base import HarnessAdapter
from cli._local_state import get_home


@dataclass(frozen=True)
class CompanionResult:
    """Outcome of the companion install/sync step."""

    installed: bool
    skill_dir: str | None
    course_id: str | None
    version_id: str | None
    already: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "installed": self.installed,
            "skill_dir": self.skill_dir,
            "course_id": self.course_id,
            "version_id": self.version_id,
            "already": self.already,
        }


class CompanionNotFoundError(RuntimeError):
    """Raised when no companion bundle source can be located."""


def locate_bundle_dir(args: argparse.Namespace) -> Path | None:
    """Resolve the companion bundle source directory.

    Order: ``--companion-source`` flag →
    ``$LOGION_COMPANION_BUNDLE_SOURCE`` env →
    newest dir under ``$LOGION_HOME/companion-bundles/`` → None.
    """
    source = getattr(args, "companion_source", None)
    if source is not None:
        path = Path(source)
        return path if path.is_dir() else None

    env_source = __import__("os").environ.get("LOGION_COMPANION_BUNDLE_SOURCE")
    if env_source:
        path = Path(env_source)
        if path.is_dir():
            return path

    bundles_root = get_home() / "companion-bundles"
    if not bundles_root.is_dir():
        return None

    candidates = sorted(
        (p for p in bundles_root.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def install_companion(
    args: argparse.Namespace, adapter: HarnessAdapter
) -> CompanionResult:
    """Install the companion bundle and symlink it into adapter.skill_dir().

    The canonical install is delegated to
    ``handle_skills_install`` with a Namespace carrying
    ``--source=<bundle_dir>`` and ``--symlink-dir=adapter.skill_dir()``.
    Idempotent: a re-run over an unchanged bundle returns
    ``already=True`` with ``installed=False``.
    """
    bundle_dir = locate_bundle_dir(args)
    if bundle_dir is None:
        raise CompanionNotFoundError(
            "no companion bundle directory found — "
            "set --companion-source or place a bundle under "
            f"{get_home() / 'companion-bundles'}"
        )

    target_skill_dir = adapter.skill_dir()
    target_skill_dir.mkdir(parents=True, exist_ok=True)

    # Read the skill name from the bundle's SKILL.md frontmatter.
    from cli.commands.skills._agent_symlink import (
        create_symlink,
        read_skill_name,
    )

    skill_name = read_skill_name(bundle_dir)
    if not skill_name:
        raise CompanionNotFoundError(
            f"bundle at {bundle_dir} has no readable skill name in SKILL.md"
        )

    link_path = target_skill_dir / skill_name
    if link_path.is_symlink() and link_path.resolve() == bundle_dir.resolve():
        return CompanionResult(
            installed=False,
            skill_dir=str(target_skill_dir),
            course_id=None,
            version_id=None,
            already=True,
        )

    create_symlink(target_skill_dir, skill_name, bundle_dir)
    return CompanionResult(
        installed=True,
        skill_dir=str(target_skill_dir),
        course_id=None,
        version_id=None,
        already=False,
    )


def resolve_target_adapter(args: argparse.Namespace):
    """Resolve the adapter for the companion step."""
    from cli._harness.custom import CustomPathHarness

    agent_dir = getattr(args, "agent_dir", None)
    if agent_dir:
        return CustomPathHarness(Path(agent_dir).expanduser())

    harness = getattr(args, "harness", None)
    if harness:
        return get_adapter(harness)

    present = detect_present()
    return present[0] if present else None


CLOSING_COPY = (
    "\nYou're ready to use Logion with your agent.\n"
    "  - Search courses:  logion listings search \"<query>\"\n"
    "  - Install a skill:  logion skills install <course-id>\n"
    "  - Buy a course:    logion courses purchase <course-id>\n"
    "  - Browse installed: logion skills installed\n"
)

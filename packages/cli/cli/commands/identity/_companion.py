# SPDX-License-Identifier: MIT
"""Companion-bundle step for ``identity onboarding``.

Locates the companion bundle directory, delegates the canonical install
to the existing ``handle_skills_install`` path (so the bundle lands in
``$LOGION_HOME/installed/`` with a manifest, content hash, and real
``course_id``/``version_id``), and symlinks the installed directory
into the chosen harness's ``skill_dir``.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from cli._errors import print_err
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


class CompanionInstallError(RuntimeError):
    """Raised when the canonical install step fails."""


# Stable identifiers for the first-party companion.  The bundle's
# ``SKILL.md`` carries the human-readable name; the marketplace IDs are
# constants so onboarding can record them without a remote lookup.
COMPANION_COURSE_ID = "logion-marketplace-companion"
COMPANION_VERSION_ID = "latest"


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

    env_source = os.environ.get("LOGION_COMPANION_BUNDLE_SOURCE")
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


def _already_installed(course_id: str, version_id: str) -> Path | None:
    """Return the installed dir if the companion is already installed."""
    from cli._local_state import installed_dir

    try:
        dest = installed_dir(course_id, version_id, get_home())
    except Exception:
        return None
    return dest if dest.is_dir() else None


def install_companion(
    args: argparse.Namespace, adapter: HarnessAdapter
) -> CompanionResult:
    """Install the companion bundle and symlink it into the harness skill dir.

    Delegates the canonical install to ``handle_skills_install`` with a
    Namespace carrying ``--source=<bundle_dir>``,
    ``--symlink-dir=adapter.skill_dir()``, and
    ``--install-source=logion-marketplace``.  Idempotent: a re-run over
    an unchanged bundle returns ``already=True`` with ``installed=False``.
    """
    bundle_dir = locate_bundle_dir(args)
    if bundle_dir is None:
        raise CompanionNotFoundError(
            "no companion bundle directory found — "
            "set --companion-source or place a bundle under "
            f"{get_home() / 'companion-bundles'}"
        )

    course_id = COMPANION_COURSE_ID
    version_id = COMPANION_VERSION_ID

    # If already installed canonically, just ensure the symlink points
    # at the existing install dir.
    existing = _already_installed(course_id, version_id)
    if existing is not None:
        _ensure_symlink(adapter, existing)
        return CompanionResult(
            installed=False,
            skill_dir=str(adapter.skill_dir()),
            course_id=course_id,
            version_id=version_id,
            already=True,
        )

    # Delegate to the canonical install path so the bundle lands under
    # $LOGION_HOME/installed/ with a manifest and content hash.
    # The install handler prints a progress line to stdout; redirect it
    # to stderr so it never corrupts ``--json`` output from onboarding.
    from cli.commands.skills.handlers import handle_skills_install

    install_args = argparse.Namespace(
        source=bundle_dir,
        course_id=course_id,
        version_id=version_id,
        title="Logion Marketplace Companion",
        target=None,
        dry_run=False,
        force=False,
        install_source="logion-marketplace",
        symlink_dir=str(adapter.skill_dir()),
        no_symlink=False,
        # Common options needed by resolve_config_from_args.
        api_key=getattr(args, "api_key", None),
        base_url=getattr(args, "base_url", None),
        json_output=getattr(args, "json_output", False),
        timeout=getattr(args, "timeout", None),
        max_retries=getattr(args, "max_retries", None),
    )

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        rc = handle_skills_install(install_args)
    # Surface install progress on stderr (non-JSON channel).
    progress = captured.getvalue().strip()
    if progress:
        sys.stderr.write(progress + "\n")
    if rc != 0:
        raise CompanionInstallError(
            f"canonical companion install failed (exit {rc})"
        )

    installed = _already_installed(course_id, version_id)
    if installed is None:
        raise CompanionInstallError(
            "canonical install reported success but the installed "
            "directory is missing"
        )

    _ensure_symlink(adapter, installed)
    return CompanionResult(
        installed=True,
        skill_dir=str(adapter.skill_dir()),
        course_id=course_id,
        version_id=version_id,
        already=False,
    )


def _ensure_symlink(adapter: HarnessAdapter, install_dest: Path) -> None:
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


CLOSING_COPY = (
    "\nYou're ready to use Logion with your agent.\n"
    '  - Search courses:  logion listings search "<query>"\n'
    "  - Install a skill:  logion skills install <course-id>\n"
    "  - Buy a course:    logion courses purchase <course-id>\n"
    "  - Browse installed: logion skills installed\n"
)

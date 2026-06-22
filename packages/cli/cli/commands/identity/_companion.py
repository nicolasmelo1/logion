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


# Stable identifier for the first-party companion course.  The version
# is read from the bundle's ``SKILL.md`` frontmatter so updates are
# tracked correctly; ``"latest"`` is only a fallback.
COMPANION_COURSE_ID = "logion-marketplace-companion"
_FALLBACK_VERSION_ID = "latest"


def _read_companion_version(bundle_dir: Path) -> str:
    """Read ``version:`` from the bundle's SKILL.md frontmatter."""
    skill_md = bundle_dir / "SKILL.md"
    if not skill_md.is_file():
        return _FALLBACK_VERSION_ID
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _FALLBACK_VERSION_ID
    if not text.startswith("---"):
        return _FALLBACK_VERSION_ID
    end = text.find("\n---", 3)
    if end < 0:
        return _FALLBACK_VERSION_ID
    block = text[3:end]
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("version:"):
            value = stripped[len("version:") :].strip().strip('"').strip("'")
            return value or _FALLBACK_VERSION_ID
    return _FALLBACK_VERSION_ID


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

    # Newest dir by mtime; skip entries that can't be stat'ed (perms,
    # broken mounts, transient FS errors) so onboarding never crashes.
    newest: tuple[float, Path] | None = None
    for entry in bundles_root.iterdir():
        try:
            if not entry.is_dir():
                continue
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest[0]:
            newest = (mtime, entry)
    return newest[1] if newest else None


def _already_installed(course_id: str, version_id: str) -> Path | None:
    """Return the installed dir if the companion is already installed."""
    from cli._local_state import UnsafeIdentifierError, installed_dir

    try:
        dest = installed_dir(course_id, version_id, get_home())
    except UnsafeIdentifierError:
        return None  # invalid course/version segment → not installed
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
    version_id = _read_companion_version(bundle_dir)

    # If already installed canonically, check whether the content
    # matches.  Only return ``already=True`` when the bundle is
    # unchanged; a different bundle triggers a re-install.
    existing = _already_installed(course_id, version_id)
    if existing is not None:
        from cli._local_state import read_manifest
        from cli.commands.skills._install_helpers import (
            collect_installable_files,
            compute_content_hash,
        )

        manifest = read_manifest(course_id, version_id, get_home())
        existing_hash = ""
        if isinstance(manifest, dict):
            existing_hash = manifest.get("content_sha256", "")
        new_hash = compute_content_hash(
            collect_installable_files(bundle_dir), root=bundle_dir
        )
        if existing_hash and new_hash == existing_hash:
            from ._onboarding_helpers import ensure_symlink as _ensure_symlink

            _ensure_symlink(adapter, existing)
            return CompanionResult(
                installed=False,
                skill_dir=str(adapter.skill_dir()),
                course_id=course_id,
                version_id=version_id,
                already=True,
            )
        # Content differs → fall through to re-install with --force.

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
        # Force overwrite when the companion is already installed but
        # the bundle content differs (checked above).
        force=existing is not None,
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

    from ._onboarding_helpers import ensure_symlink as _ensure_symlink

    _ensure_symlink(adapter, installed)
    return CompanionResult(
        installed=True,
        skill_dir=str(adapter.skill_dir()),
        course_id=course_id,
        version_id=version_id,
        already=False,
    )


CLOSING_COPY = (
    "\nYou're ready to use Logion with your agent.\n"
    '  - Search courses:  logion listings search "<query>"\n'
    "  - Install a skill:  logion skills install <course-id>\n"
    "  - Buy a course:    logion courses purchase <course-id>\n"
    "  - Browse installed: logion skills installed\n"
)

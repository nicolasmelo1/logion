# SPDX-License-Identifier: MIT
"""Companion-bundle step for ``identity onboarding``."""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
from dataclasses import dataclass
from pathlib import Path

from cli._first_party import (
    LOGION_MARKETPLACE_COMPANION_COURSE_ID,
    LOGION_MARKETPLACE_COMPANION_NAME,
)
from cli._harness.base import HarnessAdapter
from cli._json import opt_str
from cli._local_state import get_home

from ._companion_source import locate_bundle_source, materialize_bundle


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


COMPANION_COURSE_ID = LOGION_MARKETPLACE_COMPANION_COURSE_ID
_FALLBACK_VERSION_ID = "latest"


def _read_skill_frontmatter_value(
    bundle_dir: Path,
    field: str,
    fallback: str,
) -> str:
    """Read a scalar frontmatter field from the bundle's SKILL.md."""
    skill_md = bundle_dir / "SKILL.md"
    if not skill_md.is_file():
        return fallback
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return fallback
    if not text.startswith("---"):
        return fallback
    end = text.find("\n---", 3)
    if end < 0:
        return fallback
    block = text[3:end]
    prefix = f"{field}:"
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            value = stripped[len(prefix) :].strip().strip('"').strip("'")
            return value or fallback
    return fallback


def _read_companion_version(bundle_dir: Path) -> str:
    """Read ``version:`` from the bundle's SKILL.md frontmatter."""
    return _read_skill_frontmatter_value(
        bundle_dir,
        "version",
        _FALLBACK_VERSION_ID,
    )


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
    """Install the companion bundle and copy it into the harness skill dir.

    Resolves the source (a bundle dir, a ``*.tar.gz``, or a dir holding
    one companion tarball), extracting a tarball when needed, then
    delegates the canonical install to ``handle_skills_install`` with a
    Namespace carrying ``--source=<bundle_dir>``,
    ``--install-source=logion-marketplace``.  Idempotent: a re-run over
    an unchanged bundle returns ``already=True`` with ``installed=False``
    after refreshing the harness copy.
    """
    source = locate_bundle_source(args)
    if source is None:
        explicit = getattr(args, "companion_source", None)
        if explicit is not None:
            raise CompanionNotFoundError(
                "--companion-source is not a bundle directory or a "
                f".tar.gz file: {explicit}"
            )
        raise CompanionNotFoundError(
            "no companion bundle source found — "
            "set --companion-source (a bundle dir or .tar.gz) or place a "
            f"bundle under {get_home() / 'companion-bundles'}"
        )

    # Keep the extracted temp dir (for tarball sources) alive for the
    # whole install via the context manager.
    with materialize_bundle(source) as bundle_dir:
        return _install_from_dir(args, adapter, bundle_dir)


def _install_from_dir(
    args: argparse.Namespace,
    adapter: HarnessAdapter,
    bundle_dir: Path,
) -> CompanionResult:
    """Install a materialized companion bundle directory."""
    course_id = COMPANION_COURSE_ID
    version_id = _read_companion_version(bundle_dir)
    skill_name = _read_skill_frontmatter_value(
        bundle_dir,
        "name",
        COMPANION_COURSE_ID,
    )

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
            existing_hash = opt_str(manifest, "content_sha256", "")
        new_hash = compute_content_hash(
            collect_installable_files(bundle_dir), root=bundle_dir
        )
        if existing_hash and new_hash == existing_hash:
            from ._onboarding_helpers import ensure_symlink as _ensure_symlink

            _ensure_symlink(adapter, existing, skill_name=skill_name)
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
        title=LOGION_MARKETPLACE_COMPANION_NAME,
        target=None,
        dry_run=False,
        # Force overwrite when the companion is already installed but
        # the bundle content differs (checked above).
        force=existing is not None,
        install_source="logion-marketplace",
        symlink_dir=None,
        no_symlink=True,
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

    _ensure_symlink(adapter, installed, skill_name=skill_name)
    return CompanionResult(
        installed=True,
        skill_dir=str(adapter.skill_dir()),
        course_id=course_id,
        version_id=version_id,
        already=False,
    )

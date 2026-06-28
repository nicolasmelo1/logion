# SPDX-License-Identifier: MIT
"""Resolve and materialize the companion bundle source.

The companion step accepts three source shapes so the same code path
works for a checked-out bundle directory, a downloaded release tarball
(the real ``curl | sh`` installer fetches one), and the dev rig's
``companion-bundle/`` directory that holds a single built tarball:

- a directory containing ``SKILL.md`` — used as-is;
- a ``*.tar.gz`` file — extracted on demand;
- a directory holding exactly one
  ``logion-marketplace-companion-*.tar.gz`` — that tarball is extracted.

``materialize_bundle`` is a context manager so the extracted temp dir
stays alive for the whole install and is cleaned up afterwards.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import tarfile
import tempfile
from collections.abc import Iterator
from pathlib import Path

from cli._local_state import get_home

_COMPANION_TARBALL_GLOB = "logion-marketplace-companion-*.tar.gz"


def _is_valid_source(path: Path) -> bool:
    """A directory (validated downstream) or a ``*.tar.gz`` file."""
    if path.is_dir():
        return True
    return path.is_file() and path.name.endswith(".tar.gz")


def locate_bundle_source(args: argparse.Namespace) -> Path | None:
    """Resolve the companion bundle source (a dir or a tarball).

    Order: ``--companion-source`` flag →
    ``$LOGION_COMPANION_BUNDLE_SOURCE`` env →
    newest dir under ``$LOGION_HOME/companion-bundles/`` → None.

    The returned path may be a bundle directory, a companion ``*.tar.gz``
    file, or a directory holding exactly one companion tarball;
    ``materialize_bundle`` normalizes all three to a bundle directory.
    """
    source = getattr(args, "companion_source", None)
    if source is not None:
        path = Path(source)
        return path if _is_valid_source(path) else None

    env_source = os.environ.get("LOGION_COMPANION_BUNDLE_SOURCE")
    if env_source:
        path = Path(env_source)
        if _is_valid_source(path):
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


def _find_companion_tarball(directory: Path) -> Path | None:
    """Return the single companion tarball in *directory*, else None."""
    try:
        tarballs = sorted(directory.glob(_COMPANION_TARBALL_GLOB))
    except OSError:
        return None
    return tarballs[0] if len(tarballs) == 1 else None


def _bundle_root(extracted: Path) -> Path:
    """Return the dir holding ``SKILL.md`` after extraction.

    ``package_skill.py`` builds tarballs under a top-level
    ``logion-marketplace-companion-<version>/`` prefix, so descend into a
    lone prefix subdir when ``SKILL.md`` isn't at the extraction root.
    """
    if (extracted / "SKILL.md").is_file():
        return extracted
    subdirs = [p for p in extracted.iterdir() if p.is_dir()]
    if len(subdirs) == 1 and (subdirs[0] / "SKILL.md").is_file():
        return subdirs[0]
    return extracted


def _tarball_for(source: Path) -> Path | None:
    """Return the tarball to extract for *source*, or None for a dir."""
    if source.is_file() and source.name.endswith(".tar.gz"):
        return source
    if source.is_dir() and not (source / "SKILL.md").is_file():
        return _find_companion_tarball(source)
    return None


@contextlib.contextmanager
def materialize_bundle(source: Path) -> Iterator[Path]:
    """Yield a bundle directory for *source*, extracting a tarball if needed.

    A directory that already contains ``SKILL.md`` is yielded unchanged.
    A tarball (or a directory holding exactly one companion tarball) is
    extracted into a temporary directory — using ``tarfile``'s ``data``
    filter for path-traversal safety — and the resolved bundle root is
    yielded. The temp dir is removed when the context exits.
    """
    tarball = _tarball_for(source)
    if tarball is None:
        # Plain directory; the install validates SKILL.md downstream and
        # emits a clear error if it's missing.
        yield source
        return

    with tempfile.TemporaryDirectory(prefix="logion-companion-") as tmp:
        dest = Path(tmp)
        with tarfile.open(tarball, "r:gz") as tf:
            tf.extractall(dest, filter="data")
        yield _bundle_root(dest)

"""File-system resolver for package-map include/exclude patterns."""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from pathlib import Path

from .models import PackageMap, ResolvedFileSet


def resolve_includes(pm: PackageMap, root: Path) -> ResolvedFileSet:
    """Walk the filesystem under *root* applying include/exclude patterns.

    Exclude wins over include.  All resolved paths are relative to
    *root* and validated to be traversal-free (no ``..`` components,
    no absolute paths).

    Parameters
    ----------
    pm:
        The :class:`PackageMap` whose source/runtime/evals patterns to
        apply.
    root:
        Filesystem root to walk.
    """
    includes: list[str] = []
    excludes: list[str] = []

    if pm.source:
        includes.extend(pm.source.include)
        excludes.extend(pm.source.exclude)
    if pm.runtime:
        includes.extend(pm.runtime.include)
        excludes.extend(pm.runtime.exclude)
    if pm.evals:
        includes.extend(pm.evals.include)
        excludes.extend(pm.evals.exclude)

    # If no includes specified, include everything
    if not includes:
        includes = ["**"]

    # Walk the filesystem
    all_files: list[str] = []
    root = root.resolve()

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        # Validate: no traversal
        if _is_traversal(rel):
            continue
        all_files.append(rel)

    # Apply include/exclude
    included: list[str] = []
    for f in all_files:
        if _matches_any(f, includes) and not _matches_any(f, excludes):
            included.append(f)

    return ResolvedFileSet(
        includes=tuple(includes),
        excludes=tuple(excludes),
        files=tuple(sorted(included)),
    )


def _is_traversal(path: str) -> bool:
    """True if the path has ``..`` segments or is absolute."""
    if path.startswith("/"):
        return True
    parts = path.split("/")
    return ".." in parts


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    """True if *path* matches any of the glob *patterns*."""
    return any(fnmatch.fnmatch(path, p) for p in patterns)

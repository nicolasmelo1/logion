# SPDX-License-Identifier: MIT
"""CLI-local surface over the shared ``logion_skillmap`` package.

The parser/validator/inference engine live in ``logion_skillmap`` (shared
with the indexer and the backend materializer).  This module is the
thin CLI adapter: it re-exports the schema surface, walks a local
directory into the source-agnostic ``TreeEntry`` form ``infer`` expects,
and serializes an inferred :class:`PackageMap` back to canonical nested
YAML.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import yaml
from logion_skillmap import (
    MAX_COMPONENT_CAPABILITIES,
    MAX_INCLUDE_PATTERNS,
    PACKAGE_MAP_FILENAME,
    PACKAGE_MAP_SCHEMA_VERSION,
    InferenceResult,
    PackageMap,
    TreeEntry,
    check_unknown_keys_raw,
    infer,
    parse_package_map,
    resolve_includes,
    validate_package_map,
)

__all__ = [
    "MAX_COMPONENT_CAPABILITIES",
    "MAX_INCLUDE_PATTERNS",
    "PACKAGE_MAP_FILENAME",
    "PACKAGE_MAP_SCHEMA_VERSION",
    "InferenceResult",
    "PackageMap",
    "TreeEntry",
    "check_unknown_keys_raw",
    "dump_package_map",
    "infer",
    "package_map_to_dict",
    "parse_package_map",
    "resolve_includes",
    "validate_package_map",
    "walk_local_tree",
]

# Directories never descended into when walking a local repo.
_SKIP_DIRS = frozenset({".git"})


def walk_local_tree(
    root: Path,
) -> tuple[list[TreeEntry], Callable[[str], bytes]]:
    """Walk *root* into ``(tree, read_blob)`` for :func:`infer`.

    Only file (``blob``) entries are emitted; paths are POSIX-relative to
    *root*.  ``read_blob`` reads a file's bytes on demand (returning
    ``b""`` for anything outside the walked tree).
    """
    root = root.resolve()
    tree: list[TreeEntry] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            abs_path = Path(dirpath) / name
            rel = abs_path.relative_to(root).as_posix()
            try:
                size: int | None = abs_path.stat().st_size
            except OSError:
                size = None
            tree.append(TreeEntry(path=rel, type="blob", size=size))
    tree.sort(key=lambda e: e.path)

    def read_blob(path: str) -> bytes:
        target = (root / path).resolve()
        # Never read outside the walked root.
        if root not in target.parents and target != root:
            return b""
        try:
            return target.read_bytes()
        except OSError:
            return b""

    return tree, read_blob


def _capability_to_dict(c) -> dict:
    entry: dict = {"entrypoint": c.entrypoint}
    if c.capabilities_manifest:
        entry["capabilities_manifest"] = c.capabilities_manifest
    if c.description:
        entry["description"] = c.description
    if c.dependencies:
        entry["dependencies"] = [
            {"capability": d.capability, "reason": d.reason}
            for d in c.dependencies
        ]
    if c.include:
        entry["include"] = list(c.include)
    if c.exclude:
        entry["exclude"] = list(c.exclude)
    return entry


def _components_to_dict(pm: PackageMap) -> dict:
    components: dict = {
        "capabilities": {
            c.name: _capability_to_dict(c) for c in pm.capabilities
        }
    }
    if pm.runtime is not None:
        runtime: dict = {}
        if pm.runtime.include:
            runtime["include"] = list(pm.runtime.include)
        if pm.runtime.exclude:
            runtime["exclude"] = list(pm.runtime.exclude)
        if pm.runtime.entrypoint:
            runtime["entrypoint"] = pm.runtime.entrypoint
        components["runtime"] = runtime
    if pm.source is not None:
        components["source"] = {
            "include": list(pm.source.include),
            "exclude": list(pm.source.exclude),
        }
    if pm.evals is not None:
        components["evals"] = {
            "include": list(pm.evals.include),
            "exclude": list(pm.evals.exclude),
            "commands": dict(pm.evals.commands),
        }
    return components


def package_map_to_dict(pm: PackageMap) -> dict:
    """Serialize a :class:`PackageMap` to the canonical nested mapping."""
    return {
        "version": pm.version,
        "package": {"slug": pm.slug},
        "components": _components_to_dict(pm),
    }


def dump_package_map(pm: PackageMap) -> str:
    """Render a :class:`PackageMap` as canonical nested YAML."""
    return yaml.safe_dump(
        package_map_to_dict(pm),
        sort_keys=False,
        default_flow_style=False,
    )

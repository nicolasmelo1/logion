"""Package-map YAML parser and validator.

The skillmap package is stdlib-only, but PyYAML is available at the
call-site (the CLI layer loads the YAML and passes the text).  However,
``parse_package_map`` does accept raw YAML text and uses
``yaml.safe_load`` because the workspace already depends on PyYAML.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence

import yaml

from .models import (
    CapabilityEntry,
    EvalsBlock,
    MapWarning,
    PackageMap,
    RuntimeBlock,
    SourceBlock,
)

_KNOWN_TOP_KEYS: frozenset[str] = frozenset({
    "version",
    "slug",
    "capabilities",
    "runtime",
    "source",
    "evals",
})

_GLOB_RE = re.compile(r"^[A-Za-z0-9_.\-*/]+$")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_package_map(text: str) -> PackageMap:
    """Parse a YAML string into a :class:`PackageMap`."""
    data = yaml.safe_load(text)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise TypeError(
            "package map YAML must resolve to a mapping, "
            f"got {type(data).__name__}"
        )
    return _build_package_map(data)


def _build_package_map(data: dict) -> PackageMap:
    caps_raw = data.get("capabilities", []) or []
    capabilities = tuple(_build_capability(c) for c in caps_raw)

    runtime = None
    if "runtime" in data and data["runtime"] is not None:
        runtime = _build_runtime(data["runtime"])

    source = None
    if "source" in data and data["source"] is not None:
        source = _build_source(data["source"])

    evals = None
    if "evals" in data and data["evals"] is not None:
        evals = _build_evals(data["evals"])

    return PackageMap(
        version=int(data.get("version", 1)),
        slug=str(data.get("slug", "")),
        capabilities=capabilities,
        runtime=runtime,
        source=source,
        evals=evals,
    )


def _build_capability(c: dict) -> CapabilityEntry:
    return CapabilityEntry(
        name=str(c.get("name", "")),
        entrypoint=str(c.get("entrypoint", "")),
        capabilities_manifest=c.get("capabilities_manifest"),
        dependencies=tuple(str(d) for d in (c.get("dependencies") or [])),
        description=c.get("description"),
    )


def _build_runtime(r: dict) -> RuntimeBlock:
    return RuntimeBlock(
        include=tuple(r.get("include", []) or []),
        exclude=tuple(r.get("exclude", []) or []),
        entrypoint=r.get("entrypoint"),
    )


def _build_source(s: dict) -> SourceBlock:
    return SourceBlock(
        include=tuple(s.get("include", []) or []),
        exclude=tuple(s.get("exclude", []) or []),
    )


def _build_evals(e: dict) -> EvalsBlock:
    return EvalsBlock(
        include=tuple(e.get("include", []) or []),
        exclude=tuple(e.get("exclude", []) or []),
        commands=dict(e.get("commands", {}) or {}),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_package_map(pm: PackageMap) -> list[MapWarning]:
    """Run all validation checks on *pm*, returning warnings."""
    warnings: list[MapWarning] = []
    warnings.extend(_check_unknown_keys(pm))
    warnings.extend(_check_version(pm))
    warnings.extend(_check_empty_capabilities(pm))
    warnings.extend(_check_entrypoint_traversal(pm))
    warnings.extend(_check_entrypoint_not_matched(pm))
    warnings.extend(_check_dependency_unknown(pm))
    warnings.extend(_check_dependency_cycle(pm))
    warnings.extend(_check_glob_invalid(pm))
    warnings.extend(_check_commands_not_executed(pm))
    return warnings


def _warn(code: str, path: str, message: str) -> MapWarning:
    return MapWarning(code=code, path=path, message=message)


# -- individual checks -----------------------------------------------------


def _check_unknown_keys(pm: PackageMap) -> list[MapWarning]:  # noqa: ARG001
    """Reject unknown top-level keys.

    Unknown keys are caught at parse time by ``check_unknown_keys_raw``
    when raw YAML data is available.  This stub exists so the check
    name is always represented in the validator dispatch table.
    """
    return []


def check_unknown_keys_raw(data: dict) -> list[MapWarning]:
    """Validate unknown top-level keys from raw YAML data."""
    warnings: list[MapWarning] = []
    for key in data:
        if key not in _KNOWN_TOP_KEYS:
            warnings.append(
                _warn(
                    "package_map_unknown_keys",
                    key,
                    f"unknown top-level key: {key!r}",
                )
            )
    return warnings


def _check_version(pm: PackageMap) -> list[MapWarning]:
    if pm.version != 1:
        return [
            _warn(
                "package_map_unsupported_version",
                "version",
                f"unsupported version: {pm.version} (only version 1 "
                "is supported)",
            )
        ]
    return []


def _check_empty_capabilities(pm: PackageMap) -> list[MapWarning]:
    if not pm.capabilities:
        return [
            _warn(
                "package_map_empty_capabilities",
                "capabilities",
                "capabilities list must not be empty",
            )
        ]
    return []


def _check_entrypoint_traversal(pm: PackageMap) -> list[MapWarning]:
    warnings: list[MapWarning] = []
    for cap in pm.capabilities:
        for label, value in [
            ("entrypoint", cap.entrypoint),
            ("capabilities_manifest", cap.capabilities_manifest),
        ]:
            if value is None:
                continue
            if value.startswith("/"):
                warnings.append(
                    _warn(
                        "package_map_entrypoint_traversal",
                        f"capabilities.{cap.name}.{label}",
                        f"{label} must be relative, got absolute "
                        f"path: {value!r}",
                    )
                )
            if ".." in value.split("/"):
                warnings.append(
                    _warn(
                        "package_map_entrypoint_traversal",
                        f"capabilities.{cap.name}.{label}",
                        f"{label} must not contain '..' traversal: {value!r}",
                    )
                )
    # Also check runtime.entrypoint
    if pm.runtime and pm.runtime.entrypoint:
        ep = pm.runtime.entrypoint
        if ep.startswith("/"):
            warnings.append(
                _warn(
                    "package_map_entrypoint_traversal",
                    "runtime.entrypoint",
                    f"runtime.entrypoint must be relative, "
                    f"got absolute path: {ep!r}",
                )
            )
        if ".." in ep.split("/"):
            warnings.append(
                _warn(
                    "package_map_entrypoint_traversal",
                    "runtime.entrypoint",
                    f"runtime.entrypoint must not contain '..' "
                    f"traversal: {ep!r}",
                )
            )
    return warnings


def _check_entrypoint_not_matched(pm: PackageMap) -> list[MapWarning]:
    warnings: list[MapWarning] = []
    all_includes = _collect_includes(pm)
    for cap in pm.capabilities:
        for label, value in [
            ("entrypoint", cap.entrypoint),
            ("capabilities_manifest", cap.capabilities_manifest),
        ]:
            if value is None or not value:
                continue
            if not _path_matches_any(value, all_includes):
                warnings.append(
                    _warn(
                        "package_map_entrypoint_not_matched",
                        f"capabilities.{cap.name}.{label}",
                        f"{label} {value!r} is not matched by any "
                        "include pattern",
                    )
                )
    return warnings


def _collect_includes(pm: PackageMap) -> list[str]:
    includes: list[str] = []
    if pm.source and pm.source.include:
        includes.extend(pm.source.include)
    if pm.runtime and pm.runtime.include:
        includes.extend(pm.runtime.include)
    # If no includes at all, everything matches.
    if not includes:
        return ["**"]
    return includes


def _path_matches_any(path: str, patterns: Sequence[str]) -> bool:
    """True if *path* matches any of the glob *patterns*."""
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _check_dependency_unknown(pm: PackageMap) -> list[MapWarning]:
    warnings: list[MapWarning] = []
    known = {cap.name for cap in pm.capabilities}
    for cap in pm.capabilities:
        for dep in cap.dependencies:
            if dep not in known:
                warnings.append(
                    _warn(
                        "package_map_dependency_unknown",
                        f"capabilities.{cap.name}.dependencies",
                        f"dependency {dep!r} references an "
                        "undeclared capability",
                    )
                )
    return warnings


def _check_dependency_cycle(pm: PackageMap) -> list[MapWarning]:
    """Detect dependency cycles using DFS."""
    graph: dict[str, set[str]] = {
        cap.name: set(cap.dependencies) for cap in pm.capabilities
    }
    if not graph:
        return []

    cycle_nodes = _find_cycle_nodes(graph)
    if not cycle_nodes:
        return []

    return [
        _warn(
            "package_map_dependency_cycle",
            "capabilities",
            f"dependency cycle detected among: {sorted(cycle_nodes)}",
        )
    ]


def _find_cycle_nodes(
    graph: dict[str, set[str]],
) -> set[str]:
    """DFS cycle detection returning nodes involved in cycles."""
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(graph, white)
    cycle_nodes: set[str] = set()

    def _dfs(node: str) -> bool:
        color[node] = gray
        for dep in graph.get(node, set()):
            if dep not in color:
                continue
            if color[dep] == gray:
                cycle_nodes.add(dep)
                return True
            if color[dep] == white and _dfs(dep):
                cycle_nodes.add(node)
                return True
        color[node] = black
        return False

    for node in graph:
        if color[node] == white:
            _dfs(node)
    return cycle_nodes


def _check_glob_invalid(pm: PackageMap) -> list[MapWarning]:
    warnings: list[MapWarning] = []
    all_patterns = _collect_all_patterns(pm)
    for location, pattern in all_patterns:
        if not _GLOB_RE.match(pattern):
            warnings.append(
                _warn(
                    "package_map_glob_invalid",
                    location,
                    f"invalid glob pattern: {pattern!r}",
                )
            )
    return warnings


def _collect_all_patterns(pm: PackageMap) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    if pm.source:
        for p in pm.source.include:
            results.append(("source.include", p))
        for p in pm.source.exclude:
            results.append(("source.exclude", p))
    if pm.runtime:
        for p in pm.runtime.include:
            results.append(("runtime.include", p))
        for p in pm.runtime.exclude:
            results.append(("runtime.exclude", p))
    if pm.evals:
        for p in pm.evals.include:
            results.append(("evals.include", p))
        for p in pm.evals.exclude:
            results.append(("evals.exclude", p))
    return results


def _check_commands_not_executed(pm: PackageMap) -> list[MapWarning]:
    warnings: list[MapWarning] = []
    if pm.evals and pm.evals.commands:
        warnings.append(
            _warn(
                "package_map_commands_not_executed",
                "evals.commands",
                "evals.commands are stored but will not be executed locally",
            )
        )
    return warnings

"""Package-map YAML parser and validator.

The map is nested::

    version: 1
    package:
      slug: my-package
    components:
      capabilities:            # mapping keyed by capability name
        pr-review:
          entrypoint: skills/pr-review/SKILL.md
          dependencies:
            - capability: diff-reading
              reason: "delegates hunk parsing"
      runtime: {include, exclude, entrypoint}
      source:  {include, exclude}
      evals:   {include, exclude, commands}

The skillmap package uses PyYAML for YAML parsing.  When the raw YAML
data is available, call :func:`check_unknown_keys_raw` to validate
unknown keys before/after constructing the structured model.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence

import yaml

from .constants import PACKAGE_MAP_SCHEMA_VERSION
from .models import (
    CapabilityEntry,
    Components,
    Dependency,
    EvalsBlock,
    MapWarning,
    Package,
    PackageMap,
    RuntimeBlock,
    SourceBlock,
)

_KNOWN_TOP_KEYS: frozenset[str] = frozenset({
    "version",
    "package",
    "components",
})
_KNOWN_PACKAGE_KEYS: frozenset[str] = frozenset({"slug"})
_KNOWN_COMPONENTS_KEYS: frozenset[str] = frozenset({
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
    """Parse a YAML string into a :class:`PackageMap`.

    Raises :class:`TypeError` when the YAML does not resolve to a
    mapping.  Structural warnings (unknown keys, unsupported version,
    traversal, …) are *not* raised here — obtain them from
    :func:`validate_package_map` (and :func:`check_unknown_keys_raw`
    when the raw YAML is available).
    """
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
    package_raw = data.get("package") or {}
    components_raw = data.get("components") or {}

    slug = ""
    if isinstance(package_raw, dict):
        slug = str(package_raw.get("slug", ""))

    caps_raw: object = {}
    runtime = source = evals = None
    if isinstance(components_raw, dict):
        caps_raw = components_raw.get("capabilities") or {}
        if components_raw.get("runtime") is not None:
            runtime = _build_runtime(components_raw["runtime"])
        if components_raw.get("source") is not None:
            source = _build_source(components_raw["source"])
        if components_raw.get("evals") is not None:
            evals = _build_evals(components_raw["evals"])

    capabilities = _build_capabilities(caps_raw)

    return PackageMap(
        version=int(data.get("version", PACKAGE_MAP_SCHEMA_VERSION)),
        package=Package(slug=slug),
        components=Components(
            capabilities=capabilities,
            runtime=runtime,
            source=source,
            evals=evals,
        ),
    )


def _build_capabilities(caps_raw: object) -> tuple[CapabilityEntry, ...]:
    """Build capability entries from the ``capabilities`` mapping.

    The canonical form is a mapping ``name -> {entrypoint, ...}``; a list
    of ``{name, ...}`` dicts is also accepted for forward tolerance.
    """
    entries: list[CapabilityEntry] = []
    if isinstance(caps_raw, dict):
        for name, body in caps_raw.items():
            entries.append(_build_capability(str(name), body or {}))
    elif isinstance(caps_raw, list):
        for body in caps_raw:
            if not isinstance(body, dict):
                continue
            entries.append(_build_capability(str(body.get("name", "")), body))
    return tuple(entries)


def _build_capability(name: str, c: dict) -> CapabilityEntry:
    return CapabilityEntry(
        name=name,
        entrypoint=str(c.get("entrypoint", "")),
        capabilities_manifest=c.get("capabilities_manifest"),
        dependencies=_build_dependencies(c.get("dependencies")),
        description=c.get("description"),
        include=tuple(str(p) for p in (c.get("include") or [])),
        exclude=tuple(str(p) for p in (c.get("exclude") or [])),
    )


def _build_dependencies(deps_raw: object) -> tuple[Dependency, ...]:
    if not isinstance(deps_raw, (list, tuple)):
        return ()
    deps: list[Dependency] = []
    for d in deps_raw:
        if isinstance(d, dict):
            deps.append(
                Dependency(
                    capability=str(d.get("capability", "")),
                    reason=str(d.get("reason", "")),
                )
            )
        else:
            deps.append(Dependency(capability=str(d)))
    return tuple(deps)


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
        commands=tuple(sorted((e.get("commands") or {}).items())),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_package_map(pm: PackageMap) -> list[MapWarning]:
    """Run all post-parse validation checks on *pm*, returning warnings.

    Unknown-key validation needs the raw YAML mapping and lives in
    :func:`check_unknown_keys_raw`; everything derivable from the parsed
    model is checked here.
    """
    warnings: list[MapWarning] = []
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


def check_unknown_keys_raw(data: dict) -> list[MapWarning]:
    """Validate unknown keys (top-level + nested) from raw YAML data."""
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
    package_raw = data.get("package")
    if isinstance(package_raw, dict):
        for key in package_raw:
            if key not in _KNOWN_PACKAGE_KEYS:
                warnings.append(
                    _warn(
                        "package_map_unknown_keys",
                        f"package.{key}",
                        f"unknown package key: {key!r}",
                    )
                )
    components_raw = data.get("components")
    if isinstance(components_raw, dict):
        for key in components_raw:
            if key not in _KNOWN_COMPONENTS_KEYS:
                warnings.append(
                    _warn(
                        "package_map_unknown_keys",
                        f"components.{key}",
                        f"unknown components key: {key!r}",
                    )
                )
    return warnings


def _check_version(pm: PackageMap) -> list[MapWarning]:
    if pm.version != PACKAGE_MAP_SCHEMA_VERSION:
        return [
            _warn(
                "package_map_unsupported_version",
                "version",
                f"unsupported version: {pm.version} (only version "
                f"{PACKAGE_MAP_SCHEMA_VERSION} is supported)",
            )
        ]
    return []


def _check_empty_capabilities(pm: PackageMap) -> list[MapWarning]:
    if not pm.capabilities:
        return [
            _warn(
                "package_map_empty_capabilities",
                "components.capabilities",
                "capabilities must not be empty",
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
            warnings.extend(
                _traversal_warnings(
                    value, f"components.capabilities.{cap.name}.{label}", label
                )
            )
    if pm.runtime and pm.runtime.entrypoint:
        warnings.extend(
            _traversal_warnings(
                pm.runtime.entrypoint,
                "components.runtime.entrypoint",
                "runtime.entrypoint",
            )
        )
    return warnings


def _traversal_warnings(
    value: str | None, path: str, label: str
) -> list[MapWarning]:
    if not value:
        return []
    warnings: list[MapWarning] = []
    if value.startswith("/"):
        warnings.append(
            _warn(
                "package_map_entrypoint_traversal",
                path,
                f"{label} must be relative, got absolute path: {value!r}",
            )
        )
    if ".." in value.split("/"):
        warnings.append(
            _warn(
                "package_map_entrypoint_traversal",
                path,
                f"{label} must not contain '..' traversal: {value!r}",
            )
        )
    return warnings


def _check_entrypoint_not_matched(pm: PackageMap) -> list[MapWarning]:
    warnings: list[MapWarning] = []
    for cap in pm.capabilities:
        includes = _collect_includes(pm, cap)
        for label, value in [
            ("entrypoint", cap.entrypoint),
            ("capabilities_manifest", cap.capabilities_manifest),
        ]:
            if not value:
                continue
            if not _path_matches_any(value, includes):
                warnings.append(
                    _warn(
                        "package_map_entrypoint_not_matched",
                        f"components.capabilities.{cap.name}.{label}",
                        f"{label} {value!r} is not matched by any "
                        "include pattern",
                    )
                )
    return warnings


def _collect_includes(pm: PackageMap, cap: CapabilityEntry) -> list[str]:
    includes: list[str] = list(cap.include)
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
            if dep.capability not in known:
                warnings.append(
                    _warn(
                        "package_map_dependency_unknown",
                        f"components.capabilities.{cap.name}.dependencies",
                        f"dependency {dep.capability!r} references an "
                        "undeclared capability",
                    )
                )
    return warnings


def _check_dependency_cycle(pm: PackageMap) -> list[MapWarning]:
    """Detect dependency cycles using DFS."""
    graph: dict[str, set[str]] = {
        cap.name: {dep.capability for dep in cap.dependencies}
        for cap in pm.capabilities
    }
    if not graph:
        return []

    cycle_nodes = _find_cycle_nodes(graph)
    if not cycle_nodes:
        return []

    return [
        _warn(
            "package_map_dependency_cycle",
            "components.capabilities",
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
    for location, pattern in _collect_all_patterns(pm):
        if not _GLOB_RE.match(pattern):
            warnings.append(
                _warn(
                    "package_map_glob_invalid",
                    location,
                    f"invalid glob pattern: {pattern!r}",
                )
            )
    return warnings


def _pat(location: str, patterns: Sequence[str]) -> list[tuple[str, str]]:
    return [(location, p) for p in patterns]


def _collect_all_patterns(pm: PackageMap) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    for cap in pm.capabilities:
        prefix = f"components.capabilities.{cap.name}"
        results += _pat(f"{prefix}.include", cap.include)
        results += _pat(f"{prefix}.exclude", cap.exclude)
    for block, name in (
        (pm.source, "source"),
        (pm.runtime, "runtime"),
        (pm.evals, "evals"),
    ):
        if block is not None:
            results += _pat(f"components.{name}.include", block.include)
            results += _pat(f"components.{name}.exclude", block.exclude)
    return results


def _check_commands_not_executed(pm: PackageMap) -> list[MapWarning]:
    if pm.evals and pm.evals.commands:
        return [
            _warn(
                "package_map_commands_not_executed",
                "components.evals.commands",
                "evals.commands are stored but will not be executed locally",
            )
        ]
    return []

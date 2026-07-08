from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TreeEntry:
    path: str  # relative path from repo root
    type: str  # "blob" or "tree"
    size: int | None = None  # bytes, None for directories


@dataclass(frozen=True)
class ResolvedFileSet:
    includes: tuple[str, ...]
    excludes: tuple[str, ...]
    files: tuple[str, ...]  # resolved file paths


@dataclass(frozen=True)
class MapWarning:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class Dependency:
    """A declared dependency of one capability on another.

    Mirrors the nested ``{capability, reason}`` form in the package-map
    schema; ``reason`` is free text and may be empty.
    """

    capability: str
    reason: str = ""


@dataclass(frozen=True)
class CapabilityEntry:
    name: str
    entrypoint: str
    capabilities_manifest: str | None = None
    dependencies: tuple[Dependency, ...] = ()
    description: str | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalsBlock:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    commands: tuple[tuple[str, str], ...] = ()  # NEVER executed


@dataclass(frozen=True)
class RuntimeBlock:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    entrypoint: str | None = None


@dataclass(frozen=True)
class SourceBlock:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class Package:
    """The ``package:`` section of the map."""

    slug: str = ""


@dataclass(frozen=True)
class Components:
    """The ``components:`` section of the map.

    ``capabilities`` is an ordered tuple; the YAML form is a mapping
    keyed by capability name, and the key becomes each entry's ``name``.
    """

    capabilities: tuple[CapabilityEntry, ...] = ()
    runtime: RuntimeBlock | None = None
    source: SourceBlock | None = None
    evals: EvalsBlock | None = None


@dataclass(frozen=True)
class PackageMap:
    """A parsed ``logion-package-map.yaml``.

    The canonical shape is nested (``package`` + ``components``); the
    ``slug``/``capabilities``/``runtime``/``source``/``evals`` properties
    are read-only conveniences so validators and resolvers can reach the
    common fields without walking the nesting.
    """

    version: int = 1
    package: Package = field(default_factory=Package)
    components: Components = field(default_factory=Components)

    @property
    def slug(self) -> str:
        return self.package.slug

    @property
    def capabilities(self) -> tuple[CapabilityEntry, ...]:
        return self.components.capabilities

    @property
    def runtime(self) -> RuntimeBlock | None:
        return self.components.runtime

    @property
    def source(self) -> SourceBlock | None:
        return self.components.source

    @property
    def evals(self) -> EvalsBlock | None:
        return self.components.evals


@dataclass(frozen=True)
class ReviewFlag:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class InferredComponent:
    name: str
    root: str
    entrypoint: str
    summary: str
    content_sha256: str
    mirrors: tuple[str, ...] = ()


@dataclass(frozen=True)
class InferenceResult:
    package_map: PackageMap
    components: tuple[InferredComponent, ...]
    needs_review: tuple[ReviewFlag, ...]
    source: str  # 'author_map' | 'plugin_manifest' | 'skill_scan'

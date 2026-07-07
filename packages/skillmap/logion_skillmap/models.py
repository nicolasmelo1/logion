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
class CapabilityEntry:
    name: str
    entrypoint: str
    capabilities_manifest: str | None = None
    dependencies: tuple[str, ...] = ()
    description: str | None = None


@dataclass(frozen=True)
class EvalsBlock:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    commands: dict[str, str] = field(default_factory=dict)  # NEVER executed


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
class PackageMap:
    version: int = 1
    slug: str = ""
    capabilities: tuple[CapabilityEntry, ...] = ()
    runtime: RuntimeBlock | None = None
    source: SourceBlock | None = None
    evals: EvalsBlock | None = None


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

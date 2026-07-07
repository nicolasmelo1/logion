"""Deterministic package-map inference engine.

Precedence (first wins):
1. ``logion-package-map.yaml`` at repo root → ``source='author_map'``
2. ``.claude-plugin/plugin.json`` or
   ``.claude-plugin/marketplace.json``
   → ``source='plugin_manifest'``
3. ``SKILL.md`` / ``skill.md`` scan → ``source='skill_scan'``
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence

import yaml

from .models import (
    CapabilityEntry,
    InferenceResult,
    InferredComponent,
    PackageMap,
    ReviewFlag,
    TreeEntry,
)
from .spec import validate_skill_frontmatter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AUTHOR_MAP = "logion-package-map.yaml"
_PLUGIN_JSON = ".claude-plugin/plugin.json"
_MARKETPLACE_JSON = ".claude-plugin/marketplace.json"
_SKILL_MD_NAMES = frozenset({"SKILL.md", "skill.md"})

_EXCLUDED_SEGMENTS = frozenset({
    "test",
    "tests",
    "fixtures",
    "fixture",
    "deprecated",
    "node_modules",
    ".git",
    ".github",
})

_LOGION_FILE_RE = re.compile(
    r"(?:^|/)logion-package-map\.ya?ml$", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slug_from_path(path: str) -> str:
    """Derive a slug from a directory path."""
    parts = path.strip("/").split("/")
    return parts[-1] if parts else ""


def _dir_of(filepath: str) -> str:
    """Return the directory portion of a file path."""
    idx = filepath.rfind("/")
    return filepath[:idx] if idx >= 0 else ""


def _is_excluded(path: str) -> bool:
    segments = path.split("/")
    return bool(_EXCLUDED_SEGMENTS.intersection(segments))


def _is_hidden(path: str) -> bool:
    """True if any segment starts with a dot (mirror heuristic)."""
    return any(seg.startswith(".") for seg in path.split("/"))


def _pick_canonical(
    group: list[tuple[str, str]],
) -> str:
    """From a list of (path, hash) entries sharing the same hash,
    pick the canonical path: non-hidden first, then shortest,
    then lexicographic."""

    def sort_key(item: tuple[str, str]) -> tuple[int, int, str]:
        path = item[0]
        return (int(_is_hidden(path)), len(path), path)

    return min(group, key=sort_key)[0]


def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from a SKILL.md file."""
    text = content.strip()
    if not text.startswith("---"):
        return {}
    # Find closing --- on its own line to avoid false matches inside YAML.
    # The opening --- may be followed by a newline, so we search from
    # position 3 onward for a line that is exactly ---.
    end = -1
    for pos in range(3, len(text)):
        if text[pos] != "\n":
            continue
        # Check if the next line starts with ---
        next_line_start = pos + 1
        next_newline = text.find("\n", next_line_start)
        if next_newline >= 0:
            line = text[next_line_start:next_newline]
        else:
            line = text[next_line_start:]
        if line.strip() == "---":
            end = pos
            break
    if end < 0:
        return {}
    fm = text[3:end]
    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


# ---------------------------------------------------------------------------
# Main inference
# ---------------------------------------------------------------------------


def infer(
    tree: Sequence[TreeEntry],
    read_blob: Callable[[str], bytes],
) -> InferenceResult:
    """Infer a :class:`PackageMap` from a repository tree.

    Parameters
    ----------
    tree:
        A flat list of :class:`TreeEntry` objects describing the
        repo.
    read_blob:
        Callable that returns the bytes of a file given its path.
    """
    paths = {e.path for e in tree}

    # ---- Precedence 1: author map ---------------------------------------
    if _AUTHOR_MAP in paths:
        blob = read_blob(_AUTHOR_MAP)
        from .parser import (
            parse_package_map,
            validate_package_map,
        )

        pm = parse_package_map(blob.decode("utf-8", errors="replace"))
        components = tuple(
            InferredComponent(
                name=cap.name,
                root=_dir_of(cap.entrypoint),
                entrypoint=cap.entrypoint,
                summary=cap.description or "",
                content_sha256=_sha256(
                    read_blob(cap.entrypoint)
                    if cap.entrypoint in paths
                    else b""
                ),
                mirrors=(),
            )
            for cap in pm.capabilities
        )
        warnings = validate_package_map(pm)
        review_flags = tuple(
            ReviewFlag(code=w.code, path=w.path, message=w.message)
            for w in warnings
        )
        return InferenceResult(
            package_map=pm,
            components=components,
            needs_review=review_flags,
            source="author_map",
        )

    # ---- Precedence 2: plugin manifest ----------------------------------
    plugin_paths = [c for c in (_PLUGIN_JSON, _MARKETPLACE_JSON) if c in paths]
    if plugin_paths:
        manifest_path = plugin_paths[0]
        blob = read_blob(manifest_path)
        try:
            manifest = json.loads(blob.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            manifest = {}
        skill_paths = _extract_plugin_skills(manifest, tree)
        if skill_paths is not None:
            return _build_from_candidates(
                skill_paths,
                tree,
                read_blob,
                source="plugin_manifest",
            )

    # ---- Precedence 3: SKILL.md scan ------------------------------------
    skill_dirs = [
        _dir_of(e.path)
        for e in tree
        if e.path.split("/")[-1] in _SKILL_MD_NAMES
    ]
    seen: set[str] = set()
    unique_dirs: list[str] = []
    for d in skill_dirs:
        if d not in seen:
            seen.add(d)
            unique_dirs.append(d)

    return _build_from_candidates(
        unique_dirs, tree, read_blob, source="skill_scan"
    )


def _extract_plugin_skills(
    manifest: dict, tree: Sequence[TreeEntry]
) -> list[str] | None:
    """Extract skill directory paths from a plugin manifest."""
    skills = manifest.get("skills", [])
    if isinstance(skills, list):
        dirs: list[str] = []
        for s in skills:
            if isinstance(s, dict):
                path = s.get("path", s.get("entrypoint", ""))
            else:
                path = str(s)
            if path:
                dir_path = _dir_of(path) if "/" in path else path
                matching = [
                    e.path
                    for e in tree
                    if e.path.startswith(dir_path + "/") or e.path == dir_path
                ]
                if matching:
                    dirs.append(dir_path)
        return dirs if dirs else None
    return None


def _build_from_candidates(
    candidate_dirs: list[str],
    tree: Sequence[TreeEntry],
    read_blob: Callable[[str], bytes],
    *,
    source: str,
) -> InferenceResult:
    """Build an InferenceResult from candidate skill directories."""
    paths_set = {e.path for e in tree}

    # Pass 1: exclusion
    candidates = [d for d in candidate_dirs if not _is_excluded(d)]

    # Pass 2: harness-mirror dedup
    canonical_set, mirrors_map, skill_md_paths = _dedup_candidates(
        candidates, tree, read_blob, paths_set
    )

    # Passes 3-5: metadata, spec, emission
    review_flags, components, capability_entries = _emit_components(
        canonical_set,
        skill_md_paths,
        mirrors_map,
        tree,
        read_blob,
    )

    # Check for logion files inside skill directories
    review_flags.extend(_check_logion_files_in_skills(tree, canonical_set))

    # Determine slug
    slug = _infer_slug(tree)

    pm = PackageMap(
        version=1,
        slug=slug,
        capabilities=tuple(capability_entries),
    )

    return InferenceResult(
        package_map=pm,
        components=tuple(components),
        needs_review=tuple(review_flags),
        source=source,
    )


def _find_skill_md_paths(
    candidates: list[str],
    paths_set: set[str],
) -> dict[str, str]:
    """Map each candidate dir to its SKILL.md path."""
    skill_md_paths: dict[str, str] = {}
    for d in candidates:
        for name in _SKILL_MD_NAMES:
            candidate_path = f"{d}/{name}" if d else name
            if candidate_path in paths_set:
                skill_md_paths[d] = candidate_path
                break
    return skill_md_paths


def _dedup_candidates(
    candidates: list[str],
    tree: Sequence[TreeEntry],  # noqa: ARG001
    read_blob: Callable[[str], bytes],
    paths_set: set[str],
) -> tuple[set[str], dict[str, tuple[str, ...]], dict[str, str]]:
    """Pass 2: harness-mirror dedup.

    Returns (canonical_set, mirrors_map, skill_md_paths).
    """
    skill_md_paths = _find_skill_md_paths(candidates, paths_set)

    hash_groups: dict[str, list[tuple[str, str]]] = {}
    for d, skill_path in skill_md_paths.items():
        blob = read_blob(skill_path)
        h = _sha256(blob)
        hash_groups.setdefault(h, []).append((d, h))

    canonical_set: set[str] = set()
    mirrors_map: dict[str, tuple[str, ...]] = {}
    for _h, group in hash_groups.items():
        canonical = _pick_canonical(group)
        canonical_set.add(canonical)
        mirror_paths = tuple(p for p, _ in group if p != canonical)
        mirrors_map[canonical] = mirror_paths

    return canonical_set, mirrors_map, skill_md_paths


def _emit_components(
    canonical_set: set[str],
    skill_md_paths: dict[str, str],
    mirrors_map: dict[str, tuple[str, ...]],
    tree: Sequence[TreeEntry],  # noqa: ARG001
    read_blob: Callable[[str], bytes],
) -> tuple[list[ReviewFlag], list[InferredComponent], list[CapabilityEntry]]:
    """Passes 3-5: metadata, spec conformance, emission."""
    review_flags: list[ReviewFlag] = []
    components: list[InferredComponent] = []
    capability_entries: list[CapabilityEntry] = []

    for d in sorted(canonical_set):
        skill_path = skill_md_paths.get(d, "")
        if not skill_path:
            continue

        blob = read_blob(skill_path)
        content_sha256 = _sha256(blob)

        # Metadata from frontmatter
        fm = _parse_frontmatter(blob.decode("utf-8", errors="replace"))
        name = str(fm.get("name", "")) or _slug_from_path(d)
        description = fm.get("description")
        if description is not None:
            description = str(description)

        # Spec conformance
        flags = validate_skill_frontmatter(
            name=name,
            description=description,
            parent_dir=d,
            license_=fm.get("license"),
            compatibility=fm.get("compatibility"),
            metadata=fm.get("metadata"),
            allowed_tools=fm.get("allowed-tools"),
        )
        review_flags.extend(flags)

        entrypoint = skill_path
        summary = description or ""
        mirrors = mirrors_map.get(d, ())

        comp = InferredComponent(
            name=name,
            root=d,
            entrypoint=entrypoint,
            summary=summary,
            content_sha256=content_sha256,
            mirrors=mirrors,
        )
        components.append(comp)

        cap = CapabilityEntry(
            name=name,
            entrypoint=entrypoint,
            description=summary,
        )
        capability_entries.append(cap)

    return review_flags, components, capability_entries


def _check_logion_files_in_skills(
    tree: Sequence[TreeEntry],
    canonical_set: set[str],
) -> list[ReviewFlag]:
    """Flag logion-package-map files inside skill directories."""
    flags: list[ReviewFlag] = []
    for entry in tree:
        if entry.type != "blob":
            continue
        if _LOGION_FILE_RE.search(entry.path):
            for d in canonical_set:
                if entry.path.startswith(d + "/"):
                    flags.append(
                        ReviewFlag(
                            code="skillmap_logion_file_inside_skill",
                            path=entry.path,
                            message="logion-package-map file "
                            "found inside a skill directory",
                        )
                    )
    return flags


def _infer_slug(tree: Sequence[TreeEntry]) -> str:
    """Derive a default slug from the first top-level path."""
    for e in tree:
        if e.path in ("", "."):
            continue
        if "/" not in e.path:
            return e.path
    return ""

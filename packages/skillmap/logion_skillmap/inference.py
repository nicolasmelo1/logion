"""Deterministic package-map inference engine.

Precedence (first wins):
1. ``logion-package-map.yaml`` at repo root → ``source='author_map'``
2. ``.claude-plugin/plugin.json`` or
   ``.claude-plugin/marketplace.json``
   → ``source='plugin_manifest'``
3. ``SKILL.md`` / ``skill.md`` scan → ``source='skill_scan'``

Inference is pure and deterministic: same tree + blobs in, same result
out (test-pinned via double-run equality). No pass calls an LLM or the
network.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence

import yaml

from .constants import MAX_COMPONENT_CAPABILITIES
from .models import (
    CapabilityEntry,
    Components,
    InferenceResult,
    InferredComponent,
    Package,
    PackageMap,
    ReviewFlag,
    RuntimeBlock,
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

# Top-level license file names (lowercased) that satisfy the no_license check.
_LICENSE_NAMES = frozenset({
    "license",
    "license.md",
    "license.txt",
    "licence",
    "licence.md",
    "licence.txt",
    "copying",
    "copying.md",
})


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


def _top_segment(path: str) -> str:
    """First path segment (``''`` for a repo-root component)."""
    return path.split("/", 1)[0] if path else ""


def _include_for_root(root: str) -> str:
    """The include glob for a component rooted at *root*."""
    return f"{root}/**" if root else "**"


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


def _parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from a SKILL.md file.

    Returns the parsed mapping, or ``None`` when frontmatter is absent or
    unparsable (so callers can flag ``skillmap_frontmatter_missing``).
    """
    text = content.strip()
    if not text.startswith("---"):
        return None
    # Find closing --- on its own line to avoid false matches inside YAML.
    end = -1
    for pos in range(3, len(text)):
        if text[pos] != "\n":
            continue
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
        return None
    fm = text[3:end]
    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data


# ---------------------------------------------------------------------------
# Main inference
# ---------------------------------------------------------------------------


def infer(
    tree: Sequence[TreeEntry],
    read_blob: Callable[[str], bytes],
    *,
    slug: str | None = None,
) -> InferenceResult:
    """Infer a :class:`PackageMap` from a repository tree.

    Parameters
    ----------
    tree:
        A flat list of :class:`TreeEntry` objects describing the repo.
    read_blob:
        Callable that returns the bytes of a file given its path.
    slug:
        Optional caller override for the emitted ``package.slug``; when
        ``None`` the slug is derived deterministically from the tree.
    """
    paths = {e.path for e in tree}

    # ---- Precedence 1: author map ---------------------------------------
    if _AUTHOR_MAP in paths:
        return _infer_from_author_map(tree, read_blob)

    # ---- Precedence 2: plugin manifest ----------------------------------
    plugin_paths = [c for c in (_PLUGIN_JSON, _MARKETPLACE_JSON) if c in paths]
    if plugin_paths:
        manifest_path = plugin_paths[0]
        blob = read_blob(manifest_path)
        try:
            manifest = json.loads(blob.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            manifest = {}
        skill_paths, missing = _extract_plugin_skills(manifest, tree)
        if skill_paths is not None:
            missing_flags = [
                ReviewFlag(
                    code="manifest_path_missing",
                    path=m,
                    message=f"manifest skill path {m!r} does not exist "
                    "in the tree",
                )
                for m in missing
            ]
            return _build_from_candidates(
                skill_paths,
                tree,
                read_blob,
                source="plugin_manifest",
                slug=slug,
                extra_flags=missing_flags,
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
        unique_dirs, tree, read_blob, source="skill_scan", slug=slug
    )


def _infer_from_author_map(
    tree: Sequence[TreeEntry],
    read_blob: Callable[[str], bytes],
) -> InferenceResult:
    """Precedence 1: parse and return the author-provided map verbatim."""
    from .parser import (
        check_unknown_keys_raw,
        parse_package_map,
        validate_package_map,
    )

    paths = {e.path for e in tree}
    text = read_blob(_AUTHOR_MAP).decode("utf-8", errors="replace")
    pm = parse_package_map(text)
    raw = yaml.safe_load(text)
    raw = raw if isinstance(raw, dict) else {}

    components = tuple(
        InferredComponent(
            name=cap.name,
            root=_dir_of(cap.entrypoint),
            entrypoint=cap.entrypoint,
            summary=cap.description or "",
            content_sha256=_sha256(
                read_blob(cap.entrypoint) if cap.entrypoint in paths else b""
            ),
            mirrors=(),
        )
        for cap in pm.capabilities
    )
    warnings = check_unknown_keys_raw(raw) + validate_package_map(pm)
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


def _extract_plugin_skills(
    manifest: dict, tree: Sequence[TreeEntry]
) -> tuple[list[str] | None, list[str]]:
    """Extract skill directory paths from a plugin manifest.

    Returns ``(dirs, missing)`` where *dirs* is the list of resolvable
    skill directories (or ``None`` if the manifest declares no skills) and
    *missing* is the list of declared paths that don't exist in the tree.
    """
    skills = manifest.get("skills", [])
    if not isinstance(skills, list):
        return None, []
    dirs: list[str] = []
    missing: list[str] = []
    for s in skills:
        if isinstance(s, dict):
            path = s.get("path", s.get("entrypoint", ""))
        else:
            path = str(s)
        if not path:
            continue
        raw = str(path).rstrip("/")
        # A manifest entry is a skill *directory*; only strip to the dir
        # when it points directly at a SKILL.md file.
        if raw.split("/")[-1] in _SKILL_MD_NAMES:
            dir_path = _dir_of(raw)
        else:
            dir_path = raw
        matching = any(
            e.path.startswith(dir_path + "/") or e.path == dir_path
            for e in tree
        )
        if matching:
            dirs.append(dir_path)
        else:
            missing.append(dir_path)
    return (dirs if dirs else None), missing


def _build_from_candidates(
    candidate_dirs: list[str],
    tree: Sequence[TreeEntry],
    read_blob: Callable[[str], bytes],
    *,
    source: str,
    slug: str | None = None,
    extra_flags: Sequence[ReviewFlag] = (),
) -> InferenceResult:
    """Build an InferenceResult from candidate skill directories."""
    paths_set = {e.path for e in tree}
    review_flags: list[ReviewFlag] = list(extra_flags)

    # Pass 1: exclusion (drop + flag excluded candidates)
    candidates: list[str] = []
    for d in candidate_dirs:
        if _is_excluded(d):
            review_flags.append(
                ReviewFlag(
                    code="skillmap_excluded_segment",
                    path=d,
                    message=f"candidate {d!r} dropped: path contains an "
                    "excluded segment",
                )
            )
        else:
            candidates.append(d)

    # Pass 2: harness-mirror dedup
    canonical_set, mirrors_map, skill_md_paths = _dedup_candidates(
        candidates, read_blob, paths_set
    )

    # Passes 3-5: metadata, spec, emission
    emit_flags, components, capability_entries = _emit_components(
        canonical_set,
        skill_md_paths,
        mirrors_map,
        read_blob,
    )
    review_flags.extend(emit_flags)

    # Repo-level review flags (deterministic, order-stable).
    all_skill_dirs = set(canonical_set)
    for mirror_dirs in mirrors_map.values():
        all_skill_dirs.update(mirror_dirs)
    review_flags.extend(_check_logion_files_in_skills(tree, all_skill_dirs))
    review_flags.extend(
        _repo_level_flags(tree, canonical_set, len(components))
    )

    resolved_slug = slug if slug is not None else _infer_slug(tree)
    pm = PackageMap(
        version=1,
        package=Package(slug=resolved_slug),
        components=Components(
            capabilities=tuple(capability_entries),
            runtime=_build_runtime(components),
        ),
    )

    return InferenceResult(
        package_map=pm,
        components=tuple(components),
        needs_review=tuple(review_flags),
        source=source,
    )


def _build_runtime(
    components: list[InferredComponent],
) -> RuntimeBlock | None:
    """Emit a runtime block: primary entrypoint = first component's."""
    if not components:
        return None
    return RuntimeBlock(entrypoint=components[0].entrypoint)


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
    read_blob: Callable[[str], bytes],
    paths_set: set[str],
) -> tuple[set[str], dict[str, tuple[str, ...]], dict[str, str]]:
    """Pass 2: harness-mirror dedup.

    Returns (canonical_set, mirrors_map, skill_md_paths).
    """
    skill_md_paths = _find_skill_md_paths(candidates, paths_set)

    hash_groups: dict[str, list[tuple[str, str]]] = {}
    for d, skill_path in skill_md_paths.items():
        h = _sha256(read_blob(skill_path))
        hash_groups.setdefault(h, []).append((d, h))

    canonical_set: set[str] = set()
    mirrors_map: dict[str, tuple[str, ...]] = {}
    for group in hash_groups.values():
        canonical = _pick_canonical(group)
        canonical_set.add(canonical)
        mirrors_map[canonical] = tuple(
            sorted(p for p, _ in group if p != canonical)
        )

    return canonical_set, mirrors_map, skill_md_paths


def _emit_components(
    canonical_set: set[str],
    skill_md_paths: dict[str, str],
    mirrors_map: dict[str, tuple[str, ...]],
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

        # Pass 3: metadata from frontmatter
        fm = _parse_frontmatter(blob.decode("utf-8", errors="replace"))
        if fm is None:
            review_flags.append(
                ReviewFlag(
                    code="skillmap_frontmatter_missing",
                    path=skill_path,
                    message="SKILL.md has no parsable YAML frontmatter",
                )
            )
            fm = {}
        name = str(fm.get("name", "")) or _slug_from_path(d)
        description = fm.get("description")
        if description is not None:
            description = str(description)

        # Pass 4: spec conformance
        review_flags.extend(
            validate_skill_frontmatter(
                name=name,
                description=description,
                parent_dir=d,
                license_=fm.get("license"),
                compatibility=fm.get("compatibility"),
                metadata=fm.get("metadata"),
                allowed_tools=fm.get("allowed-tools"),
            )
        )

        # Pass 5: emission
        summary = description or ""
        components.append(
            InferredComponent(
                name=name,
                root=d,
                entrypoint=skill_path,
                summary=summary,
                content_sha256=content_sha256,
                mirrors=mirrors_map.get(d, ()),
            )
        )
        capability_entries.append(
            CapabilityEntry(
                name=name,
                entrypoint=skill_path,
                description=summary,
                include=(_include_for_root(d),),
            )
        )

    return review_flags, components, capability_entries


def _check_logion_files_in_skills(
    tree: Sequence[TreeEntry],
    skill_dirs: set[str],
) -> list[ReviewFlag]:
    """Flag logion-package-map files inside skill directories."""
    flags: list[ReviewFlag] = []
    for entry in tree:
        if entry.type != "blob":
            continue
        if not _LOGION_FILE_RE.search(entry.path):
            continue
        for d in skill_dirs:
            if entry.path.startswith(d + "/"):
                flags.append(
                    ReviewFlag(
                        code="skillmap_logion_file_inside_skill",
                        path=entry.path,
                        message="logion-package-map file found inside a "
                        "skill directory",
                    )
                )
                break
    return flags


def _repo_level_flags(
    tree: Sequence[TreeEntry],
    canonical_set: set[str],
    component_count: int,
) -> list[ReviewFlag]:
    """Closed-question review flags derived from the whole repo."""
    flags: list[ReviewFlag] = []

    if not _has_license(tree):
        flags.append(
            ReviewFlag(
                code="no_license",
                path="",
                message="no top-level LICENSE file found",
            )
        )

    if canonical_set:
        if all(_is_hidden(d) for d in canonical_set):
            flags.append(
                ReviewFlag(
                    code="hidden_tree_only",
                    path="",
                    message="all canonical skill roots live under hidden "
                    "(dot-prefixed) directories",
                )
            )
        top_trees = {_top_segment(d) for d in canonical_set}
        if len(top_trees) >= 2:
            flags.append(
                ReviewFlag(
                    code="ambiguous_primary_tree",
                    path="",
                    message="canonical skills span multiple disjoint "
                    f"top-level trees: {sorted(top_trees)}",
                )
            )

    if component_count > MAX_COMPONENT_CAPABILITIES:
        flags.append(
            ReviewFlag(
                code="skillmap_component_cap_exceeded",
                path="",
                message=f"{component_count} components exceed the "
                f"{MAX_COMPONENT_CAPABILITIES} soft cap",
            )
        )

    return flags


def _has_license(tree: Sequence[TreeEntry]) -> bool:
    for e in tree:
        if e.type != "blob":
            continue
        if "/" in e.path:
            continue
        if e.path.lower() in _LICENSE_NAMES:
            return True
    return False


def _infer_slug(tree: Sequence[TreeEntry]) -> str:
    """Derive a default slug from the first top-level path."""
    for e in tree:
        if e.path in ("", "."):
            continue
        if "/" not in e.path:
            return e.path
    return ""

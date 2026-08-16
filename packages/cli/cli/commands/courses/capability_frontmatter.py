# SPDX-License-Identifier: MIT
"""Import Logion capability manifests from SKILL.md frontmatter.

``course/capabilities.yaml`` is the single canonical publication contract.
SKILL.md frontmatter may seed or scaffold that file, but it is not a second
publication source of truth — the backend never reads SKILL.md as a fallback.

Accepted frontmatter shapes (under ``metadata``):

  metadata:
    logion:
      version: 1
      ...

  metadata:
    logion:
      capabilities:
        version: 1
        ...

Both ``metadata.logion`` and ``metadata.logion.capabilities`` may carry the
exact manifest shape, but only one may be present at a time. The extracted
mapping is passed through ``normalize_capability_manifest()`` so the result
is identical to loading ``course/capabilities.yaml`` directly.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from cli._course_capabilities import (
    CapabilityManifestError,
    normalize_capability_manifest,
)
from cli._json import JsonObject


def extract_logion_capabilities_from_skill(
    skill_path: Path,
) -> JsonObject | None:
    """Return a normalised capability manifest from SKILL.md frontmatter.

    Returns ``None`` when the file has no ``metadata.logion`` section.

    Raises :class:`CapabilityManifestError` when:
      - both ``metadata.logion`` and ``metadata.logion.capabilities`` are
        present (ambiguous — refuse rather than guess);
      - the extracted value is present but not a YAML mapping;
      - the mapping fails ``normalize_capability_manifest()``.

    Only the YAML frontmatter block delimited by the first two ``---`` lines
    at the top of the file is parsed. The Markdown body is ignored.
    """
    raw = _read_frontmatter(skill_path)
    if raw is None:
        return None
    manifest = _extract_logion_mapping(raw)
    if manifest is None:
        return None
    if not isinstance(manifest, dict):
        raise CapabilityManifestError(
            "metadata.logion capability manifest must be a mapping"
        )
    return normalize_capability_manifest(manifest)


def _read_frontmatter(skill_path: Path) -> JsonObject | None:
    """Parse the YAML frontmatter block from *skill_path*.

    Returns ``None`` if the file is missing or has no frontmatter block.
    """
    if not skill_path.is_file():
        return None
    try:
        text = skill_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    # Anchor closing delimiter to end-of-line so "\n---xyz" is not
    # mistaken for a frontmatter terminator.
    end = text.find("\n---\n", 3)
    if end < 0:
        # Handle frontmatter that is the entire file (no trailing newline).
        stripped = text.rstrip()
        if stripped.endswith("---") and text.count("---") >= 2:
            end = stripped.rfind("---")
            block = text[3:end].rstrip()
        else:
            return None
    else:
        block = text[3:end]
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise CapabilityManifestError(
            "Invalid YAML in SKILL.md frontmatter"
        ) from exc
    if not isinstance(parsed, dict):
        return None
    return parsed


def _extract_logion_mapping(
    frontmatter: JsonObject,
) -> JsonObject | None:
    """Pull the Logion capability manifest from parsed frontmatter.

    Accepts ``metadata.logion`` (direct manifest) or
    ``metadata.logion.capabilities`` (nested). Rejects having both.
    Returns ``None`` when neither is present.
    """
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        return None
    logion = metadata.get("logion")
    if logion is None:
        return None
    if not isinstance(logion, dict):
        raise CapabilityManifestError(
            "metadata.logion capability manifest must be a mapping"
        )
    direct = logion
    nested = logion.get("capabilities")
    has_direct = any(
        k in logion
        for k in (
            "version",
            "summary",
            "tools",
            "network",
            "filesystem",
            "secrets",
            "human_approval",
            "runtime",
        )
    )
    has_nested = isinstance(nested, dict)
    if has_direct and has_nested:
        raise CapabilityManifestError(
            "SKILL.md has both metadata.logion and "
            "metadata.logion.capabilities; provide only one."
        )
    if has_nested:
        return nested
    if has_direct:
        return direct
    return None

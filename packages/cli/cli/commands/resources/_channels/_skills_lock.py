# SPDX-License-Identifier: MIT
"""Strict reader for the vercel-labs ``skills`` CLI lockfile.

The canonical format is the one already pinned by the indexer adapter in
``packages/indexer/logion_indexer/adapters/skills_lock.py``::

    {
      "version": 1,
      "skills": {
        "skill-name": {
          "source": "owner/repo",
          "sourceType": "github",
          "computedHash": "sha256:..."
        }
      }
    }

Two properties matter for attribution and are enforced here rather than
guessed:

* the skill **name is the mapping key**, not a field inside the entry, so
  the mapping must never be flattened with ``.values()``;
* ``computedHash`` is a *content* digest, not a VCS revision. It can never
  be promoted to ``immutable_revision``, and it already carries its
  ``sha256:`` prefix.

Anything outside the supported version or source type raises
``UnsupportedLockfileError`` — an unknown state format fails closed
instead of silently misattributing an installation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from cli._json import JsonObject

from .._catalog_reconciliation import normalize_locator

#: Lockfile schema versions this adapter has been tested against.
SUPPORTED_LOCK_VERSIONS = frozenset({1})

#: Source types whose ``source`` is an immutable, attributable locator.
SUPPORTED_SOURCE_TYPES = frozenset({"github"})

#: An immutable manager pin, e.g. ``skills@1.4.2``. Dist-tags such as
#: ``latest`` are rejected: they cannot identify what actually ran.
_PINNED_VERSION = re.compile(r"^\d+\.\d+\.\d+[0-9A-Za-z.\-+]*$")

_SKILLS_SPEC = re.compile(r"^skills@(?P<version>.+)$")


class UnsupportedLockfileError(RuntimeError):
    """The native manager state is in a format this adapter cannot trust."""


@dataclass(frozen=True)
class SkillsLockEntry:
    """One attributable entry from ``skills-lock.json``."""

    name: str
    source: str
    source_type: str
    content_digest: str
    revision: str
    installed_paths: tuple[str, ...]


def manager_version_from_argv(argv: list[str]) -> str:
    """Extract the pinned ``skills`` version Logion is about to invoke.

    The lockfile records no manager version, so the authoritative identity
    for a Logion-delegated acquisition is the spec we execute. A floating
    dist-tag is refused rather than recorded as ``unknown``.
    """
    for token in argv:
        match = _SKILLS_SPEC.match(token)
        if match is None:
            continue
        version = match.group("version")
        if not _PINNED_VERSION.match(version):
            raise UnsupportedLockfileError(
                "resource_native_tool_version_unsupported: "
                f"skills@{version} is not an immutable version pin"
            )
        return version
    raise UnsupportedLockfileError(
        "resource_native_tool_unsupported: argv carries no skills@ spec"
    )


def _normalized_digest(raw: object) -> str:
    """Return a ``sha256:``-prefixed digest without ever double-prefixing."""
    value = str(raw or "").strip()
    if not value:
        return ""
    if value.startswith("sha256:"):
        return value
    if re.fullmatch(r"[0-9a-f]{64}", value):
        return f"sha256:{value}"
    raise UnsupportedLockfileError(
        f"unrecognized computedHash format: {value!r}"
    )


#: Where the `skills` CLI installs into the project.
_NATIVE_SKILLS_DIR = Path(".agents/skills")


def _entry_paths(name: str, info: JsonObject) -> tuple[str, ...]:
    """Local install paths for one entry, relative to the project root.

    ``skillPath`` is the skill's location *inside the upstream repository*
    and says nothing about where it landed locally, so it is never used as
    an install path — the manager's own project directory is.
    """
    raw = info.get("paths") or info.get("installedPaths")
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list):
        paths = tuple(item for item in raw if isinstance(item, str))
        if paths:
            return paths
    return (str(_NATIVE_SKILLS_DIR / name),)


def parse_skills_lock(path: Path) -> list[SkillsLockEntry]:
    """Parse ``skills-lock.json``, failing closed on an untrusted shape."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnsupportedLockfileError(
            "skills-lock.json is unreadable"
        ) from exc
    if not isinstance(raw, dict):
        raise UnsupportedLockfileError("skills-lock.json is not an object")
    version = raw.get("version")
    if version not in SUPPORTED_LOCK_VERSIONS:
        raise UnsupportedLockfileError(
            f"unsupported skills-lock.json version: {version!r} "
            f"(supported: {sorted(SUPPORTED_LOCK_VERSIONS)})"
        )
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        raise UnsupportedLockfileError(
            "skills-lock.json 'skills' is not a name-keyed object"
        )
    entries: list[SkillsLockEntry] = []
    for name, info in skills.items():
        if not isinstance(name, str) or not isinstance(info, dict):
            continue
        source_type = str(info.get("sourceType") or "")
        if source_type not in SUPPORTED_SOURCE_TYPES:
            raise UnsupportedLockfileError(
                f"unsupported skills-lock.json sourceType: {source_type!r}"
            )
        source = str(info.get("source") or "")
        if not source:
            raise UnsupportedLockfileError(
                f"skills-lock.json entry {name!r} has no source"
            )
        revision = str(info.get("revision") or info.get("commit") or "")
        entries.append(
            SkillsLockEntry(
                name=name,
                source=source,
                source_type=source_type,
                content_digest=_normalized_digest(info.get("computedHash")),
                revision=revision,
                installed_paths=_entry_paths(name, info),
            )
        )
    return entries


def select_entry(
    entries: list[SkillsLockEntry],
    *,
    expected_source: str,
    expected_name: str,
) -> SkillsLockEntry:
    """Pick the single entry matching the plan by exact identity.

    Matching is exact on both source and skill name. Substring or display
    name matching is forbidden: it silently attributes an installation to
    a neighbouring repository.
    """
    wanted = normalize_locator(expected_source)
    candidates = [
        entry
        for entry in entries
        if (not wanted or normalize_locator(entry.source) == wanted)
        and (not expected_name or entry.name == expected_name)
    ]
    if len(candidates) != 1:
        raise UnsupportedLockfileError(
            f"skills-lock.json has {len(candidates)} entries matching "
            f"source={expected_source!r} name={expected_name!r}; "
            "expected exactly 1"
        )
    return candidates[0]

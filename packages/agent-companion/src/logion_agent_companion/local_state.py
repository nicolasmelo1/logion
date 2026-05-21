"""Local installation state layout and operations.

Manages the ~/.logion/ directory structure, manifest files, compact
index, recall index, lockfile, and workflow history for the Logion
Marketplace Companion.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

DEFAULT_HOME = Path.home() / ".logion"


def get_home() -> Path:
    """Return the Logion home directory (LOGION_HOME override or default)."""
    env = os.environ.get("LOGION_HOME")
    return Path(env) if env else DEFAULT_HOME


def ensure_layout(home: Path | None = None) -> Path:
    """Create the directory layout under *home* if it does not exist.

    Returns the *home* path so callers can chain.
    """
    h = home or get_home()
    (h / "installed").mkdir(parents=True, exist_ok=True)
    return h


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

REQUIRED_MANIFEST_KEYS = frozenset({
    "course_id",
    "version_id",
    "title",
    "source",
    "installed_at",
    "entrypoint",
    "capabilities",
    "required_tools",
    "content_sha256",
    "review_status",
})

MANIFEST_OPTIONAL_KEYS = frozenset({
    "price_cents_at_install",
    "currency",
})


def validate_manifest(data: dict[str, Any]) -> list[str]:
    """Return a list of validation errors for *data*.

    An empty list means the manifest is valid.
    """
    errors: list[str] = []
    missing = REQUIRED_MANIFEST_KEYS - set(data.keys())
    for key in sorted(missing):
        errors.append(f"manifest missing required key: {key}")
    if "course_id" in data and not isinstance(data["course_id"], str):
        errors.append("course_id must be a string")
    if "version_id" in data and not isinstance(data["version_id"], str):
        errors.append("version_id must be a string")
    if "capabilities" in data and not isinstance(data["capabilities"], list):
        errors.append("capabilities must be a list")
    if "required_tools" in data and not isinstance(
        data["required_tools"], list
    ):
        errors.append("required_tools must be a list")
    return errors


def sha256_of_files(paths: list[Path]) -> str:
    """Return the SHA-256 hex digest of the concatenated contents of *paths*.

    Files are read in sorted order by their relative name.
    """
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.read_bytes())
    return h.hexdigest()


def write_manifest(
    manifest: dict[str, Any],
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> Path:
    """Write *manifest* to the installed capability directory.

    Returns the path to ``manifest.json``.
    """
    h = home or get_home()
    dest = h / "installed" / course_id / version_id
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "manifest.json"
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def read_manifest(
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> dict[str, Any] | None:
    """Read the manifest for an installed capability.

    Returns ``None`` if the file does not exist or is invalid JSON.
    """
    h = home or get_home()
    path = h / "installed" / course_id / version_id / "manifest.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_installed(home: Path | None = None) -> list[dict[str, Any]]:
    """Return a list of manifest dicts for all installed capabilities."""
    h = home or get_home()
    installed_dir = h / "installed"
    if not installed_dir.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for course_dir in sorted(installed_dir.iterdir()):
        if not course_dir.is_dir():
            continue
        for version_dir in sorted(course_dir.iterdir()):
            manifest_path = version_dir / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            results.append(data)
    return results


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

INDEX_FILENAME = "index.json"


def build_index(home: Path | None = None) -> list[dict[str, Any]]:
    """Build the compact index from installed manifests.

    The index contains only IDs, titles, summaries, capabilities,
    entrypoints, versions, and required tools — no full skill bodies.
    """
    manifests = list_installed(home)
    index: list[dict[str, Any]] = []
    for m in manifests:
        index.append({
            "course_id": m.get("course_id", ""),
            "version_id": m.get("version_id", ""),
            "title": m.get("title", ""),
            "entrypoint": m.get("entrypoint", "SKILL.md"),
            "capabilities": m.get("capabilities", []),
            "required_tools": m.get("required_tools", []),
            "review_status": m.get("review_status", ""),
        })
    return index


def write_index(
    index: list[dict[str, Any]],
    home: Path | None = None,
) -> Path:
    """Write the compact index to ``index.json``."""
    h = home or get_home()
    ensure_layout(h)
    path = h / INDEX_FILENAME
    path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def read_index(home: Path | None = None) -> list[dict[str, Any]]:
    """Read the compact index from ``index.json``.

    Returns an empty list if the file does not exist.
    """
    h = home or get_home()
    path = h / INDEX_FILENAME
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


# ---------------------------------------------------------------------------
# Recall
# ---------------------------------------------------------------------------

RECALL_FILENAME = "recall.json"

DANGEROUS_RECALL_TERMS = frozenset({
    "delete",
    "remove",
    "drop",
    "rm",
    "force",
    "sudo",
    "chmod",
    "exec",
})


def _has_danger_flags(commands: list[str] | None) -> list[str]:
    """Return danger flags for command strings."""
    if commands is None:
        return []
    flags: list[str] = []
    for cmd in commands:
        lower = cmd.lower()
        for term in DANGEROUS_RECALL_TERMS:
            if term in lower:
                flags.append(term)
                break
    return sorted(set(flags))


def build_recall_entries(
    installed: list[dict[str, Any]],
    workflows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build recall entries from installed manifests and workflows.

    Each entry is compact with provenance and confidence — no full
    skill bodies or secrets.
    """
    entries: list[dict[str, Any]] = []

    for m in installed:
        entries.append({
            "type": "installed_capability",
            "id": m.get("course_id", ""),
            "title": m.get("title", ""),
            "summary": m.get("summary", "")[:200],
            "confidence": 0.91,
            "source": "installed_index",
            "entrypoint": (
                f"installed/{m['course_id']}/{m['version_id']}"
                f"/{m.get('entrypoint', 'SKILL.md')}"
            ),
            "danger_flags": [],
        })

    if workflows:
        for w in workflows:
            entries.append({
                "type": "workflow",
                "id": w.get("id", ""),
                "title": w.get("title", ""),
                "confidence": w.get("confidence", 0.5),
                "source": "workflow_history",
                "commands": w.get("commands", []),
                "success_count": w.get("success_count", 0),
                "last_success_at": w.get("last_success_at", ""),
                "danger_flags": _has_danger_flags(w.get("commands")),
            })

    return entries


def write_recall(
    entries: list[dict[str, Any]],
    home: Path | None = None,
) -> Path:
    """Write recall index to ``recall.json``."""
    h = home or get_home()
    ensure_layout(h)
    path = h / RECALL_FILENAME
    path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def read_recall(home: Path | None = None) -> list[dict[str, Any]]:
    """Read recall index from ``recall.json``.

    Returns an empty list if the file does not exist.
    """
    h = home or get_home()
    path = h / RECALL_FILENAME
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def search_recall(
    query: str,
    home: Path | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search the recall index for *query* (case-insensitive).

    Returns up to *limit* entries ranked by a simple keyword match
    score.  Each result includes ``confidence`` adjusted by match
    quality.
    """
    entries = read_recall(home)
    if not entries or not query:
        return []

    q_lower = query.lower()
    scored: list[tuple[float, dict[str, Any]]] = []

    for entry in entries:
        score = 0.0
        title = entry.get("title", "").lower()
        summary = entry.get("summary", "").lower()
        eid = entry.get("id", "").lower()

        if q_lower in title:
            score += 0.5
        if q_lower in summary:
            score += 0.3
        if q_lower in eid:
            score += 0.2

        if entry.get("type") == "workflow":
            for cmd in entry.get("commands", []):
                if q_lower in cmd.lower():
                    score += 0.4
                    break

        if score > 0:
            adjusted = min(
                entry.get("confidence", 0.5) * (1 + score),
                1.0,
            )
            entry_copy = {**entry, "confidence": round(adjusted, 2)}
            scored.append((score, entry_copy))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------

LOCK_FILENAME = "lock.json"


def acquire_lock(
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> Path:
    """Acquire an install lock for *course_id* / *version_id*.

    Writes a ``lock.json`` with pid and timestamp.  Returns the
    lock path.  Caller should call :func:`release_lock` when done.
    """
    h = home or get_home()
    ensure_layout(h)
    path = h / LOCK_FILENAME
    lock_data = {
        "course_id": course_id,
        "version_id": version_id,
        "pid": os.getpid(),
        "locked_at": _utc_iso_now(),
    }
    path.write_text(
        json.dumps(lock_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def read_lock(home: Path | None = None) -> dict[str, Any] | None:
    """Read the current lock.  Returns ``None`` if no lock file exists."""
    h = home or get_home()
    path = h / LOCK_FILENAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def release_lock(home: Path | None = None) -> bool:
    """Remove the lock file.  Returns ``True`` if removed."""
    h = home or get_home()
    path = h / LOCK_FILENAME
    if path.is_file():
        path.unlink()
        return True
    return False


def is_locked(home: Path | None = None) -> bool:
    """Return ``True`` if a lock file exists."""
    return read_lock(home) is not None


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

WORKFLOWS_FILENAME = "workflows.json"


def read_workflows(home: Path | None = None) -> list[dict[str, Any]]:
    """Read workflow history.  Returns empty list if no file."""
    h = home or get_home()
    path = h / WORKFLOWS_FILENAME
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def append_workflow(
    workflow: dict[str, Any],
    home: Path | None = None,
) -> Path:
    """Append *workflow* to the workflows file and return the path."""
    h = home or get_home()
    ensure_layout(h)
    path = h / WORKFLOWS_FILENAME
    workflows = read_workflows(h)
    workflows.append(workflow)
    path.write_text(
        json.dumps(workflows, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_iso_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    import datetime

    return datetime.datetime.now(datetime.UTC).isoformat()


def main() -> int:
    """Dump the local state layout for debugging."""
    import logging

    h = ensure_layout()
    log = logging.getLogger(__name__)
    log.info("Logion home: %s", h)
    log.info("  installed/:  %s", (h / "installed").is_dir())
    log.info("  index.json:  %s", (h / "index.json").is_file())
    log.info("  recall.json: %s", (h / "recall.json").is_file())
    log.info("  lock.json:   %s", (h / "lock.json").is_file())
    log.info("  workflows.json: %s", (h / "workflows.json").is_file())
    return 0


if __name__ == "__main__":
    sys.exit(main())

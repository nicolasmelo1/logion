"""Local installation state layout and operations.

Manages the ~/.logion/ directory structure, manifest files, compact
index, recall index, lockfile, and workflow history for the Logion
Marketplace Companion.

State files use a top-level envelope::

    {"schema_version": 1, "entries": [...]}

Reads accept the legacy bare-list form for forward compatibility.
"""

from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

DEFAULT_HOME = Path.home() / ".logion"

SCHEMA_VERSION = 1

# Identifiers (course_id, version_id) become path segments and lock
# filenames.  Restrict to a safe character set and reject traversal
# sequences before they reach the filesystem.
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class UnsafeIdentifierError(ValueError):
    """Raised when course_id/version_id contains unsafe characters."""


def _safe_segment(value: str, kind: str = "identifier") -> str:
    """Validate *value* as a safe single-segment identifier.

    Rejects path separators, ``..``, leading dot, control characters,
    empty strings, and anything outside ``[A-Za-z0-9._-]``.  Returns the
    value unchanged so callers can use it inline.
    """
    if not isinstance(value, str) or not _SAFE_SEGMENT_RE.fullmatch(value):
        raise UnsafeIdentifierError(
            f"unsafe {kind}: {value!r} (must match [A-Za-z0-9._-], "
            "max 128 chars, no path separators or '..')"
        )
    if value in (".", "..") or ".." in value:
        raise UnsafeIdentifierError(f"unsafe {kind}: {value!r}")
    return value


def get_home() -> Path:
    """Return the Logion home directory (LOGION_HOME override or default)."""
    env = os.environ.get("LOGION_HOME")
    return Path(env) if env else DEFAULT_HOME


def ensure_layout(home: Path | None = None) -> Path:
    """Create the directory layout under *home* if it does not exist."""
    h = home or get_home()
    (h / "installed").mkdir(parents=True, exist_ok=True)
    return h


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------


def _wrap(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "entries": entries}


def _unwrap(raw: Any) -> list[dict[str, Any]]:
    """Return entries from envelope or legacy bare-list form."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("entries"), list):
        return raw["entries"]
    return []


def _read_json_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        return _unwrap(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return []


def _atomic_write_text(path: Path, text: str) -> None:
    """Write *text* to *path* atomically (tmp file + rename).

    Prevents truncated/half-written JSON if the process is interrupted
    mid-write; readers either see the previous content or the new
    content, never a partial buffer.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()


def _write_json_entries(path: Path, entries: list[dict[str, Any]]) -> Path:
    _atomic_write_text(
        path,
        json.dumps(_wrap(entries), indent=2, ensure_ascii=False) + "\n",
    )
    return path


# ---------------------------------------------------------------------------
# Secret masking
# ---------------------------------------------------------------------------

SECRET_KEY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"password|passwd", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"bearer", re.IGNORECASE),
    re.compile(r"^auth$|_auth$|auth_", re.IGNORECASE),
)

MASK_PLACEHOLDER = "***MASKED***"

# String-level redaction patterns for command-line secrets.  Applied to
# free-text fields (notably workflow ``commands``) before they hit
# recall.json, because key-name masking alone cannot catch a secret
# embedded in a positional argument like ``curl -H "Authorization:
# Bearer ghp_..."`` or ``./deploy --token=abc123``.
COMMAND_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Authorization: Bearer <token>  /  Authorization: Basic <b64>
    re.compile(
        r"(?i)(authorization:\s*(?:bearer|basic|token)\s+)\S+",
    ),
    # --token=..., --api-key=..., --password=..., -p=...
    re.compile(
        r"(?i)(--(?:api[_-]?key|token|password|passwd|secret|"
        r"credential|bearer|auth)[=\s]+)(?:\"[^\"]+\"|'[^']+'|\S+)",
    ),
    # KEY=value style env exports for known secret env names
    re.compile(
        r"(?i)\b((?:AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN|API_KEY|"
        r"BEARER_TOKEN|PASSWORD)=)\S+",
    ),
    # Common token shapes (GitHub, Stripe, OpenAI, generic JWT-ish)
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b"),
    re.compile(r"\b(sk-[A-Za-z0-9-]{16,})\b"),
    re.compile(
        r"\b(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+)\b"
    ),
)


def mask_command_string(value: str) -> str:
    """Redact common command-line secret shapes from *value*.

    Used on workflow ``commands`` before they are written to
    recall.json so a captured shell line like
    ``curl -H 'Authorization: Bearer ghp_abc' …`` does not persist
    the bearer token unmasked.  Pattern matching is conservative —
    over-masking is preferred to under-masking.
    """
    for pat in COMMAND_SECRET_PATTERNS:
        # Each pattern either has one capture group (prefix to keep) or
        # captures the whole match; mask everything after the prefix.
        def _sub(m: re.Match[str]) -> str:
            if m.groups():
                return f"{m.group(1)}{MASK_PLACEHOLDER}"
            return MASK_PLACEHOLDER

        value = pat.sub(_sub, value)
    return value


def _looks_like_secret_key(key: str) -> bool:
    return any(p.search(key) for p in SECRET_KEY_PATTERNS)


def mask_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *data* with secret-like fields masked.

    Walks nested dicts and lists.  String values under keys that match
    :data:`SECRET_KEY_PATTERNS` are replaced with
    :data:`MASK_PLACEHOLDER`.  Non-string values under those keys are
    also masked.
    """
    return _mask_value(data)  # type: ignore[return-value]


def _mask_value(value: Any, parent_key: str | None = None) -> Any:
    if parent_key is not None and _looks_like_secret_key(parent_key):
        return MASK_PLACEHOLDER
    if isinstance(value, dict):
        return {k: _mask_value(v, parent_key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(item, parent_key=parent_key) for item in value]
    return value


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


def validate_manifest(data: dict[str, Any]) -> list[str]:
    """Return validation errors for *data*; empty list means valid."""
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


_HASH_CHUNK = 64 * 1024  # 64 KiB — keeps peak memory bounded for big files.


def sha256_of_files(
    paths: list[Path],
    root: Path | None = None,
) -> str:
    """SHA-256 over *paths* including each file's relative path.

    Reads each file in :data:`_HASH_CHUNK`-sized chunks so peak memory
    stays bounded regardless of file size — important for
    ``verify_installed_content`` running across large installed
    bundles.  Each file contributes
    ``<rel_path>\\0<length>\\0<bytes>\\0`` so a rename, repartition, or
    reordering changes the digest.  When *root* is provided, paths are
    taken relative to it; otherwise the file name alone is used.
    """
    h = hashlib.sha256()
    for p in sorted(paths):
        if root is not None:
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                rel = p.name
        else:
            rel = p.name
        size = p.stat().st_size
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(size).encode("ascii"))
        h.update(b"\0")
        with p.open("rb") as fh:
            while True:
                chunk = fh.read(_HASH_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
        h.update(b"\0")
    return h.hexdigest()


def _installed_files(version_dir: Path) -> list[Path]:
    """Return on-disk files for an installed version, excluding manifest."""
    return sorted(
        p
        for p in version_dir.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    )


def installed_dir(course_id: str, version_id: str, home: Path) -> Path:
    """Resolve the install path with sanitized identifiers.

    Rejects path-traversal in *course_id* / *version_id* and guarantees
    the result stays under ``home/installed/``.
    """
    _safe_segment(course_id, "course_id")
    _safe_segment(version_id, "version_id")
    root = (home / "installed").resolve()
    dest = (root / course_id / version_id).resolve()
    # Defence in depth: even with the regex above, confirm the resolved
    # path did not escape the installed root.
    try:
        dest.relative_to(root)
    except ValueError as exc:
        raise UnsafeIdentifierError(
            f"resolved install path escapes home: {dest}"
        ) from exc
    return dest


def write_manifest(
    manifest: dict[str, Any],
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> Path:
    """Write *manifest* to the installed capability directory."""
    h = home or get_home()
    dest = installed_dir(course_id, version_id, h)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "manifest.json"
    _atomic_write_text(
        path,
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    )
    return path


def read_manifest(
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> dict[str, Any] | None:
    """Read an installed capability's manifest, or ``None`` if absent."""
    h = home or get_home()
    try:
        dest = installed_dir(course_id, version_id, h)
    except UnsafeIdentifierError:
        return None
    path = dest / "manifest.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_installed(home: Path | None = None) -> list[dict[str, Any]]:
    """Return manifest dicts for all installed capabilities."""
    h = home or get_home()
    installed_root = h / "installed"
    if not installed_root.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for course_dir in sorted(installed_root.iterdir()):
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


def compute_installed_hash(
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> str:
    """Re-hash on-disk content for an installed version."""
    h = home or get_home()
    try:
        version_dir = installed_dir(course_id, version_id, h)
    except UnsafeIdentifierError:
        return ""
    if not version_dir.is_dir():
        return ""
    return sha256_of_files(_installed_files(version_dir), root=version_dir)


def verify_installed_content(
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> dict[str, Any]:
    """Compare manifest ``content_sha256`` to on-disk hash.

    Returns a dict with ``ok`` (bool), ``expected``, ``actual``, and
    ``user_modified`` (True when hashes diverge).  Missing manifest
    yields ``ok=False`` with empty hashes.
    """
    manifest = read_manifest(course_id, version_id, home)
    expected = (manifest or {}).get("content_sha256", "")
    actual = compute_installed_hash(course_id, version_id, home)
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "expected": expected,
        "actual": actual,
        "user_modified": bool(expected) and expected != actual,
    }


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

INDEX_FILENAME = "index.json"


def build_index(home: Path | None = None) -> list[dict[str, Any]]:
    """Build the compact index from installed manifests (no skill bodies)."""
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
    """Write the compact index to ``index.json`` (enveloped)."""
    h = home or get_home()
    ensure_layout(h)
    with state_lock(h):
        return _write_json_entries(h / INDEX_FILENAME, index)


def read_index(home: Path | None = None) -> list[dict[str, Any]]:
    """Read the compact index; empty list if absent."""
    h = home or get_home()
    return _read_json_entries(h / INDEX_FILENAME)


# ---------------------------------------------------------------------------
# Recall
# ---------------------------------------------------------------------------

RECALL_FILENAME = "recall.json"

# Closed enum of danger flags surfaced by recall.  Word-boundary regex
# avoids false positives like "rm-safe-helper" or "removeListener".
DANGER_FLAG_PATTERNS: dict[str, re.Pattern[str]] = {
    "fs_destructive": re.compile(
        r"\b(rm|rmdir|unlink|shred|mkfs|dd)\b|--force\b|\bdrop\s+table\b",
        re.IGNORECASE,
    ),
    "privilege_escalation": re.compile(
        r"\b(sudo|doas|su)\b",
        re.IGNORECASE,
    ),
    "network_exec": re.compile(
        r"(curl|wget)[^|]*\|\s*(sh|bash|zsh)\b",
        re.IGNORECASE,
    ),
    "shell_eval": re.compile(
        r"\b(eval|exec)\b",
        re.IGNORECASE,
    ),
    "permission_change": re.compile(
        r"\b(chmod|chown)\b",
        re.IGNORECASE,
    ),
}

DANGER_FLAGS: frozenset[str] = frozenset(DANGER_FLAG_PATTERNS)


def detect_danger_flags(commands: list[str] | None) -> list[str]:
    """Return sorted danger flags present in *commands*."""
    if not commands:
        return []
    found: set[str] = set()
    for cmd in commands:
        for flag, pattern in DANGER_FLAG_PATTERNS.items():
            if pattern.search(cmd):
                found.add(flag)
    return sorted(found)


def build_recall_entries(
    installed: list[dict[str, Any]],
    workflows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build compact recall entries with provenance and secret masking."""
    entries: list[dict[str, Any]] = []

    for m in installed:
        entry = {
            "type": "installed_capability",
            "id": m.get("course_id", ""),
            "title": m.get("title", ""),
            "summary": (m.get("summary", "") or "")[:200],
            "confidence": 0.91,
            "source": "installed_index",
            "entrypoint": (
                f"installed/{m.get('course_id', '')}/"
                f"{m.get('version_id', '')}/"
                f"{m.get('entrypoint', 'SKILL.md')}"
            ),
            "danger_flags": [],
        }
        entries.append(mask_secrets(entry))

    if workflows:
        for w in workflows:
            raw_commands = w.get("commands", []) or []
            # Danger-flag detection runs on the *original* string so a
            # token like ``--token=…`` does not get masked into
            # invisibility before the regex sees it.  Persisted
            # commands are the redacted form.
            danger_flags = detect_danger_flags(raw_commands)
            redacted_commands = [
                mask_command_string(c) if isinstance(c, str) else c
                for c in raw_commands
            ]
            entry = {
                "type": "workflow",
                "id": w.get("id", ""),
                "title": w.get("title", ""),
                "confidence": float(w.get("confidence", 0.5)),
                "source": "workflow_history",
                "commands": redacted_commands,
                "success_count": int(w.get("success_count", 0)),
                "last_success_at": w.get("last_success_at", ""),
                "danger_flags": danger_flags,
            }
            entries.append(mask_secrets(entry))

    return entries


def write_recall(
    entries: list[dict[str, Any]],
    home: Path | None = None,
) -> Path:
    """Write recall index to ``recall.json`` (enveloped)."""
    h = home or get_home()
    ensure_layout(h)
    with state_lock(h):
        return _write_json_entries(h / RECALL_FILENAME, entries)


def read_recall(home: Path | None = None) -> list[dict[str, Any]]:
    """Read recall entries; empty list if absent."""
    h = home or get_home()
    return _read_json_entries(h / RECALL_FILENAME)


def rebuild_recall(home: Path | None = None) -> Path:
    """Refresh recall.json from current installed manifests and workflows."""
    h = home or get_home()
    with state_lock(h):
        entries = build_recall_entries(list_installed(h), read_workflows(h))
        return write_recall(entries, h)


def search_recall(
    query: str,
    home: Path | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search recall by case-insensitive keyword; ranked top-k matches."""
    entries = read_recall(home)
    if not entries or not query:
        return []

    q_lower = query.lower()
    scored: list[tuple[float, dict[str, Any]]] = []

    for entry in entries:
        score = 0.0
        title = (entry.get("title", "") or "").lower()
        summary = (entry.get("summary", "") or "").lower()
        eid = (entry.get("id", "") or "").lower()

        if q_lower in title:
            score += 0.5
        if q_lower in summary:
            score += 0.3
        if q_lower in eid:
            score += 0.2

        if entry.get("type") == "workflow":
            for cmd in entry.get("commands", []) or []:
                if q_lower in cmd.lower():
                    score += 0.4
                    break

        if score > 0:
            adjusted = min(
                float(entry.get("confidence", 0.5)) * (1 + score),
                1.0,
            )
            entry_copy = {**entry, "confidence": round(adjusted, 2)}
            scored.append((score, entry_copy))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]


# ---------------------------------------------------------------------------
# Lockfile (per course/version)
# ---------------------------------------------------------------------------

LOCKS_DIRNAME = "locks"
STATE_LOCK_FILENAME = ".state.lock"
STATE_LOCK_RETRY_DELAY_S = 0.05
STATE_LOCK_TIMEOUT_S = 5.0


# Re-entrancy: paths this process is currently holding state-locks on.
_STATE_LOCK_HELD: set[str] = set()


@contextlib.contextmanager
def state_lock(
    home: Path | None = None,
    timeout: float = STATE_LOCK_TIMEOUT_S,
):
    """Cross-process lock for global state files (index/recall/workflows).

    Two concurrent ``logion skills install`` / ``logion recall record``
    invocations otherwise race on ``index.json`` and ``recall.json`` —
    each rebuilds from a different snapshot and the last writer wins.
    This lock serializes those rebuilds via an ``O_EXCL`` lock file in
    the Logion home directory.  Acquisition retries with a short
    sleep up to *timeout* seconds before raising ``TimeoutError``.

    Re-entrant within a single process: if this process already holds
    the lock for the same *home*, nested ``with state_lock(...)`` calls
    are no-ops.  Lets high-level routines (``record_workflow_success``,
    ``copy_and_finalize``) lock once around a sequence of low-level
    writers that each acquire the same lock defensively.

    The lock is best-effort across processes: it is removed on normal
    exit and on ``finally``; a process that crashes hard may leave a
    stale lock that the next caller will eventually time out on.
    """
    import time

    h = home or get_home()
    h.mkdir(parents=True, exist_ok=True)
    path = h / STATE_LOCK_FILENAME
    key = str(path)
    if key in _STATE_LOCK_HELD:
        yield path
        return
    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"state lock {path} held longer than {timeout}s"
                ) from None
            time.sleep(STATE_LOCK_RETRY_DELAY_S)
    _STATE_LOCK_HELD.add(key)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        yield path
    finally:
        _STATE_LOCK_HELD.discard(key)
        with contextlib.suppress(OSError):
            path.unlink()


class LockHeldError(RuntimeError):
    """Raised when ``acquire_lock`` finds an existing lock file."""

    def __init__(self, course_id: str, version_id: str, path: Path) -> None:
        super().__init__(
            f"lock already held for {course_id}/{version_id} at {path}"
        )
        self.course_id = course_id
        self.version_id = version_id
        self.path = path


def _lock_path(home: Path, course_id: str, version_id: str) -> Path:
    # Validate before composing the path.  Locks live in nested
    # directories (``locks/<course>/<version>.json``) so identifiers
    # containing ``__`` (legal under _SAFE_SEGMENT_RE) cannot collide
    # onto the same filename — e.g. ``a__b``/``c`` and ``a``/``b__c``
    # used to flatten to the same file with a ``__`` separator.
    _safe_segment(course_id, "course_id")
    _safe_segment(version_id, "version_id")
    return home / LOCKS_DIRNAME / course_id / f"{version_id}.json"


def acquire_lock(
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> Path:
    """Acquire an install lock scoped to *course_id*/*version_id*.

    Uses ``O_CREAT|O_EXCL`` so concurrent installers fail fast with
    :class:`LockHeldError` instead of silently overwriting the same
    lock file.  Locks live under ``~/.logion/locks/`` so they survive
    ``rmtree`` of the install directory during reinstall.
    """
    h = home or get_home()
    path = _lock_path(h, course_id, version_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "course_id": course_id,
        "version_id": version_id,
        "pid": os.getpid(),
        "locked_at": _utc_iso_now(),
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise LockHeldError(course_id, version_id, path) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
    except Exception:
        with contextlib.suppress(OSError):
            path.unlink()
        raise
    return path


def read_lock(
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> dict[str, Any] | None:
    """Read the lock for one course/version; ``None`` if absent."""
    h = home or get_home()
    try:
        path = _lock_path(h, course_id, version_id)
    except UnsafeIdentifierError:
        return None
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def release_lock(
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> bool:
    """Remove the lock for one course/version; ``True`` if removed.

    Tolerates the file already being gone (``FileNotFoundError``) and
    other ``OSError`` failures so a stale or concurrently-removed lock
    cannot crash a ``finally`` block (notably the one in
    :func:`copy_and_finalize`).  Returns ``False`` when the file was
    not present or could not be removed.
    """
    h = home or get_home()
    try:
        path = _lock_path(h, course_id, version_id)
    except UnsafeIdentifierError:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return True


def is_locked(
    course_id: str,
    version_id: str,
    home: Path | None = None,
) -> bool:
    """Return ``True`` if the course/version has an active lock."""
    return read_lock(course_id, version_id, home) is not None


def any_locks(home: Path | None = None) -> list[tuple[str, str]]:
    """Return ``(course_id, version_id)`` pairs with active locks."""
    h = home or get_home()
    locks_dir = h / LOCKS_DIRNAME
    if not locks_dir.is_dir():
        return []
    locks: list[tuple[str, str]] = []
    # Locks live two levels deep under ``locks/<course>/<version>.json``.
    for path in sorted(locks_dir.glob("*/*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        course = data.get("course_id")
        version = data.get("version_id")
        if isinstance(course, str) and isinstance(version, str):
            locks.append((course, version))
    return locks


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

WORKFLOWS_FILENAME = "workflows.json"


def read_workflows(home: Path | None = None) -> list[dict[str, Any]]:
    """Read workflow history; empty list if absent."""
    h = home or get_home()
    return _read_json_entries(h / WORKFLOWS_FILENAME)


def write_workflows(
    workflows: list[dict[str, Any]],
    home: Path | None = None,
) -> Path:
    """Write workflow history (enveloped)."""
    h = home or get_home()
    ensure_layout(h)
    with state_lock(h):
        return _write_json_entries(h / WORKFLOWS_FILENAME, workflows)


def record_workflow_success(
    workflow_id: str,
    title: str,
    commands: list[str],
    home: Path | None = None,
    confidence: float = 0.5,
) -> dict[str, Any]:
    """Record a successful workflow invocation.

    If a workflow with *workflow_id* exists, increments ``success_count``
    and updates ``last_success_at``.  Otherwise creates a new record.
    Always rebuilds the recall index so the new evidence is searchable.
    Returns the resulting workflow record.  The read-modify-write
    sequence and the recall rebuild are serialized via ``state_lock``
    so concurrent ``logion recall record`` calls cannot lose updates.
    """
    h = home or get_home()
    with state_lock(h):
        workflows = read_workflows(h)
        now = _utc_iso_now()
        updated: dict[str, Any] | None = None
        for w in workflows:
            if w.get("id") == workflow_id:
                w["title"] = title or w.get("title", "")
                w["commands"] = commands or w.get("commands", [])
                w["success_count"] = int(w.get("success_count", 0)) + 1
                w["last_success_at"] = now
                w["confidence"] = min(
                    float(w.get("confidence", confidence)) + 0.05, 1.0
                )
                updated = w
                break
        if updated is None:
            updated = {
                "id": workflow_id,
                "title": title,
                "commands": commands,
                "success_count": 1,
                "last_success_at": now,
                "confidence": confidence,
            }
            workflows.append(updated)

        write_workflows(workflows, h)
        rebuild_recall(h)
        return updated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_iso_now() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.UTC).isoformat()

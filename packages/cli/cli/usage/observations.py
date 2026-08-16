# SPDX-License-Identifier: MIT
"""Local usage observation spool for resource-use events.

Observations are written to ``$LOGION_HOME/usage/observations.jsonl``
as JSONL with restrictive permissions (``0700`` directory, ``0600``
file).  No free-text or path fields are stored — only opaque
identifiers and metadata.

Deduplication keys on
``(session_hash, resource_id, version_id, event)`` within a bounded
window so repeated invocations within one session are not recorded
multiple times.
"""

from __future__ import annotations

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import stat
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from cli._local_state import get_home

SCOPE_KINDS = Literal[
    "repo-current",
    "repo-parent",
    "repo-root",
    "user",
    "admin",
    "system",
    "custom",
]

EVENTS = Literal[
    "resource_invoked",
    "resource_file_read",
    "resource_tool_used",
]

DEDUP_WINDOW_SECONDS = 300  # 5 minutes


@dataclass(frozen=True)
class UsageObservation:
    """One resource-use observation record.

    No free-text or path field is stored.  All identifiers are
    opaque-local unless explicitly noted.
    """

    schema_version: Literal[1]
    observation_id: str
    observed_at: str
    harness: str
    event: Literal[
        "resource_invoked",
        "resource_file_read",
        "resource_tool_used",
    ]
    resource_id: str
    version_id: str
    resource_type: str
    acquisition_channel: str
    installation_id: str
    scope_kind: Literal[
        "repo-current",
        "repo-parent",
        "repo-root",
        "user",
        "admin",
        "system",
        "custom",
    ]
    scope_id: str
    session_hash: str | None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported observation schema version")
        if self.event not in {
            "resource_invoked",
            "resource_file_read",
            "resource_tool_used",
        }:
            raise ValueError("unsupported observation event")
        if self.scope_kind not in {
            "repo-current",
            "repo-parent",
            "repo-root",
            "user",
            "admin",
            "system",
            "custom",
        }:
            raise ValueError("unsupported observation scope")
        required = (
            self.observation_id,
            self.observed_at,
            self.harness,
            self.resource_id,
            self.version_id,
            self.resource_type,
            self.acquisition_channel,
            self.installation_id,
            self.scope_id,
        )
        if any(not value for value in required):
            raise ValueError("observation identifiers must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict for spool emission."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_jsonl(self) -> str:
        """Return a single JSONL line (no trailing newline)."""
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        )


# Fields pinned by contract — a test asserts this exact set.
OBSERVATION_FIELDS: tuple[str, ...] = (
    "schema_version",
    "observation_id",
    "observed_at",
    "harness",
    "event",
    "resource_id",
    "version_id",
    "resource_type",
    "acquisition_channel",
    "installation_id",
    "scope_kind",
    "scope_id",
    "session_hash",
)


def _utc_iso_now() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.UTC).isoformat()


def _observation_group_id(obs: UsageObservation) -> str:
    """Deterministic group id for deduplication."""
    raw = "\0".join([
        str(obs.session_hash or ""),
        obs.resource_id,
        obs.version_id,
        obs.event,
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _spool_dir(logion_home: Path | None = None) -> Path:
    """Return the usage observation spool directory."""
    home = logion_home or get_home()
    return home / "usage"


def _spool_path(logion_home: Path | None = None) -> Path:
    """Return the full path to the observations JSONL spool."""
    return _spool_dir(logion_home) / "observations.jsonl"


def _ensure_spool(path: Path) -> None:
    """Create the spool directory and file with restrictive permissions."""
    spool_dir = path.parent
    if spool_dir.is_symlink():
        raise ValueError("usage spool directory must not be a symlink")
    spool_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    spool_dir.chmod(0o700)
    if path.is_symlink():
        raise ValueError("usage spool file must not be a symlink")
    if not path.exists():
        flags = os.O_CREAT | os.O_WRONLY
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        os.close(fd)
    os.chmod(path, 0o600)


def _read_all_observations(
    logion_home: Path | None = None,
) -> list[dict[str, Any]]:
    """Read all observations from the spool file."""
    path = _spool_path(logion_home)
    if not path.is_file():
        return []
    results: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


def _is_duplicate(
    existing: list[dict[str, Any]],
    obs: UsageObservation,
) -> bool:
    """Check if *obs* duplicates an existing entry within the window."""
    now = datetime.datetime.now(datetime.UTC)
    for entry in existing:
        if (
            entry.get("session_hash") == obs.session_hash
            and entry.get("resource_id") == obs.resource_id
            and entry.get("version_id") == obs.version_id
            and entry.get("event") == obs.event
        ):
            observed_at = entry.get("observed_at")
            if not observed_at:
                continue
            try:
                prev_time = datetime.datetime.fromisoformat(
                    str(observed_at).replace("Z", "+00:00")
                )
            except ValueError:
                continue
            elapsed = (now - prev_time).total_seconds()
            if elapsed < DEDUP_WINDOW_SECONDS:
                return True
    return False


def spool_observation(
    obs: UsageObservation,
    *,
    logion_home: Path | None = None,
) -> Path | None:
    """Append *obs* to the local JSONL spool if not a duplicate.

    Returns the spool file path if written (or already present as a
    duplicate), ``None`` if writing failed.
    """
    path = _spool_path(logion_home)
    _ensure_spool(path)
    lock_path = path.with_suffix(".lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    flags = os.O_APPEND | os.O_RDWR
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("usage spool must be a regular file")
        with os.fdopen(os.dup(fd), encoding="utf-8") as handle:
            existing = [json.loads(line) for line in handle if line.strip()]
        if _is_duplicate(existing, obs):
            return path
        os.write(fd, (obs.to_jsonl() + "\n").encode())
    finally:
        os.close(fd)
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
    return path


def list_pending_observations(
    *,
    since_seconds: int | None = None,
    logion_home: Path | None = None,
) -> list[dict[str, Any]]:
    """List pending observations, optionally filtered by recency.

    Parameters
    ----------
    since_seconds:
        Only return observations newer than this many seconds.  ``None``
        returns all.
    """
    observations = _read_all_observations(logion_home)
    if since_seconds is None:
        return observations
    cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        seconds=since_seconds
    )
    pending: list[dict[str, Any]] = []
    for obs in observations:
        observed_at = obs.get("observed_at")
        if not observed_at:
            continue
        try:
            ts = datetime.datetime.fromisoformat(
                str(observed_at).replace("Z", "+00:00")
            )
        except ValueError:
            continue
        if ts >= cutoff:
            pending.append(obs)
    return pending


def dismiss_observations(
    group_id: str,
    *,
    logion_home: Path | None = None,
) -> int:
    """Remove observations matching *group_id* from the spool.

    Returns the number of observations removed.
    """
    path = _spool_path(logion_home)
    if not path.is_file():
        return 0
    lock_path = path.with_suffix(".lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        observations = _read_all_observations(logion_home)
        kept: list[dict[str, Any]] = []
        removed = 0
        for obs in observations:
            obs_obj = _dict_to_observation(obs)
            if (
                obs_obj is not None
                and _observation_group_id(obs_obj) == group_id
            ):
                removed += 1
            else:
                kept.append(obs)
        if removed:
            _rewrite_spool(path, kept)
        return removed
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _rewrite_spool(path: Path, entries: list[dict[str, Any]]) -> None:
    """Atomically rewrite the spool file with *entries*."""
    spool_dir = path.parent
    spool_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    spool_dir.chmod(0o700)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        lines = [
            json.dumps(e, sort_keys=True, separators=(",", ":"))
            for e in entries
        ]
        tmp.write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)
    finally:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()


def _dict_to_observation(
    data: dict[str, Any],
) -> UsageObservation | None:
    """Reconstruct a UsageObservation from a dict, or None if invalid."""
    try:
        return UsageObservation(
            schema_version=data.get("schema_version", 1),
            observation_id=data.get("observation_id", ""),
            observed_at=data.get("observed_at", ""),
            harness=data.get("harness", ""),
            event=data.get("event", ""),  # type: ignore[arg-type]
            resource_id=data.get("resource_id", ""),
            version_id=data.get("version_id", ""),
            resource_type=data.get("resource_type", ""),
            acquisition_channel=data.get("acquisition_channel", ""),
            installation_id=data.get("installation_id", ""),
            scope_kind=data.get("scope_kind", ""),  # type: ignore[arg-type]
            scope_id=data.get("scope_id", ""),
            session_hash=data.get("session_hash"),
        )
    except (TypeError, ValueError):
        return None


def make_observation(
    *,
    harness: str,
    event: EVENTS,
    resource_id: str,
    version_id: str,
    resource_type: str,
    acquisition_channel: str,
    installation_id: str,
    scope_kind: SCOPE_KINDS,
    scope_id: str,
    session_hash: str | None = None,
) -> UsageObservation:
    """Build a new UsageObservation with generated id and timestamp."""
    return UsageObservation(
        schema_version=1,
        observation_id=str(uuid.uuid4()),
        observed_at=_utc_iso_now(),
        harness=harness,
        event=event,
        resource_id=resource_id,
        version_id=version_id,
        resource_type=resource_type,
        acquisition_channel=acquisition_channel,
        installation_id=installation_id,
        scope_kind=scope_kind,
        scope_id=scope_id,
        session_hash=session_hash,
    )


__all__ = [
    "DEDUP_WINDOW_SECONDS",
    "OBSERVATION_FIELDS",
    "UsageObservation",
    "dismiss_observations",
    "list_pending_observations",
    "make_observation",
    "spool_observation",
]

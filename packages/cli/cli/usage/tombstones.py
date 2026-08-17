# SPDX-License-Identifier: MIT
"""Local record of what has already been reported to the API.

A harness hook fires many times per session and a companion may be
re-invoked after a crash or a resumed conversation. Without a local
tombstone the only thing standing between that and duplicate reviews is
the server's upsert, which is a deduplication backstop rather than a
consent boundary — the request still leaves the machine.

Tombstones live beside the spool under ``$LOGION_HOME/usage/`` and hold
opaque ids only.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from cli._json import JsonObject, opt_str
from cli._local_state import _atomic_write_text, get_home

FEEDBACK = "feedback"
RECEIPTS = "receipts"


def _path(logion_home: Path | None = None) -> Path:
    home = logion_home or get_home()
    return home / "usage" / "reported.json"


def _load(logion_home: Path | None = None) -> JsonObject:
    path = _path(logion_home)
    if not path.is_file() or path.is_symlink():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _section(data: JsonObject, name: str) -> dict[str, JsonObject]:
    section = data.get(name)
    if not isinstance(section, dict):
        return {}
    return {
        key: value for key, value in section.items() if isinstance(value, dict)
    }


def _save(data: JsonObject, logion_home: Path | None = None) -> None:
    path = _path(logion_home)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    _atomic_write_text(path, json.dumps(data, sort_keys=True, indent=2) + "\n")
    path.chmod(0o600)


def feedback_key(resource_id: str, version_id: str, task_class: str) -> str:
    """The identity the API also treats as one feedback row."""
    return f"{resource_id}\0{version_id}\0{task_class}"


def feedback_tombstone(
    resource_id: str,
    version_id: str,
    task_class: str,
    *,
    logion_home: Path | None = None,
) -> str | None:
    """The feedback id already submitted for this identity, if any."""
    entries = _section(_load(logion_home), FEEDBACK)
    entry = entries.get(feedback_key(resource_id, version_id, task_class))
    return opt_str(entry, "feedback_id") if entry else None


def record_feedback(
    resource_id: str,
    version_id: str,
    task_class: str,
    feedback_id: str,
    *,
    logion_home: Path | None = None,
) -> None:
    """Remember a successful feedback submission."""
    data = _load(logion_home)
    entries = _section(data, FEEDBACK)
    entries[feedback_key(resource_id, version_id, task_class)] = {
        "feedback_id": feedback_id,
        "submitted_at": _now(),
    }
    data[FEEDBACK] = dict(entries)
    _save(data, logion_home)


def receipt_tombstone(
    observation_id: str, *, logion_home: Path | None = None
) -> str | None:
    """The receipt id already uploaded for an observation, if any."""
    entry = _section(_load(logion_home), RECEIPTS).get(observation_id)
    return opt_str(entry, "receipt_id") if entry else None


def record_receipt(
    observation_id: str,
    receipt_id: str,
    *,
    logion_home: Path | None = None,
) -> None:
    """Remember that one observation has been uploaded as a receipt."""
    data = _load(logion_home)
    entries = _section(data, RECEIPTS)
    entries[observation_id] = {
        "receipt_id": receipt_id,
        "submitted_at": _now(),
    }
    data[RECEIPTS] = dict(entries)
    _save(data, logion_home)


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


__all__ = [
    "feedback_key",
    "feedback_tombstone",
    "receipt_tombstone",
    "record_feedback",
    "record_receipt",
]

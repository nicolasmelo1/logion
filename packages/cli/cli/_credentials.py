# SPDX-License-Identifier: MIT
"""Persisted CLI credentials (~/.logion/credentials.json).

Stores identity context and the agent API key so commands do not require
``--user-id`` or ``LOGION_API_KEY`` on every invocation.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

from cli._local_state import _atomic_write_text, get_home

CREDENTIALS_FILENAME = "credentials.json"

SCHEMA_VERSION = 1


def credentials_path(home: Path | None = None) -> Path:
    """Return the credentials file path under the Logion home."""
    return (home or get_home()) / CREDENTIALS_FILENAME


def read_credentials(home: Path | None = None) -> dict[str, Any]:
    """Read stored credentials; empty dict if absent or unreadable."""
    path = credentials_path(home)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def save_user_identity(
    user_id: str,
    email: str | None = None,
    home: Path | None = None,
    agent_id: str | None = None,
    api_key: str | None = None,
    api_key_prefix: str | None = None,
) -> Path:
    """Persist the user identity, preserving unrelated keys."""
    path = credentials_path(home)
    data = read_credentials(home)
    data["schema_version"] = SCHEMA_VERSION
    data["user_id"] = user_id
    if email is not None:
        data["email"] = email
    if agent_id is not None:
        data["agent_id"] = agent_id
    if api_key is not None:
        data["api_key"] = api_key
    if api_key_prefix is not None:
        data["api_key_prefix"] = api_key_prefix
    _atomic_write_text(
        path,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    )
    # Identity context is not secret, but the file is user-private state.
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)
    return path


def stored_user_id(home: Path | None = None) -> str | None:
    """Return the stored user id, or ``None`` if not set."""
    value = read_credentials(home).get("user_id")
    if isinstance(value, str) and value.strip():
        return value
    return None


def stored_agent_id(home: Path | None = None) -> str | None:
    """Return the stored agent id, or ``None`` if not set."""
    value = read_credentials(home).get("agent_id")
    if isinstance(value, str) and value.strip():
        return value
    return None


def stored_api_key(home: Path | None = None) -> str | None:
    """Return the stored API key, or ``None`` if not set."""
    value = read_credentials(home).get("api_key")
    if isinstance(value, str) and value.strip():
        return value
    return None


def stored_api_key_prefix(home: Path | None = None) -> str | None:
    """Return the stored API key prefix, or ``None`` if not set."""
    value = read_credentials(home).get("api_key_prefix")
    if isinstance(value, str) and value.strip():
        return value
    return None


def save_autoreview_consent(enabled: bool, home: Path | None = None) -> Path:
    """Persist the auto-review consent decision (non-secret)."""
    path = credentials_path(home)
    data = read_credentials(home)
    data["schema_version"] = SCHEMA_VERSION
    data["autoreview_consent"] = bool(enabled)
    _atomic_write_text(
        path, json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    )
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)
    return path


def stored_autoreview_consent(home: Path | None = None) -> bool | None:
    """Return the recorded consent, or ``None`` if never asked."""
    value = read_credentials(home).get("autoreview_consent")
    return bool(value) if isinstance(value, bool) else None


def is_onboarded(home: Path | None = None) -> bool:
    """True once a user id has been stored (drives the first-run trigger)."""
    return stored_user_id(home) is not None

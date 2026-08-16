# SPDX-License-Identifier: MIT
"""Persistent consent modes for harness observation integrations."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from cli._json import JsonObject
from cli._local_state import get_home

VALID_MODES = frozenset({"prompt", "auto", "local-only"})


def _path() -> Path:
    return get_home() / "integrations.json"


def load_states() -> dict[str, JsonObject]:
    path = _path()
    if not path.is_file() or path.is_symlink():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def get_mode(harness: str) -> str | None:
    state = load_states().get(harness)
    mode = state.get("mode") if isinstance(state, dict) else None
    return mode if mode in VALID_MODES else None


def set_mode(harness: str, mode: str | None) -> None:
    if mode is not None and mode not in VALID_MODES:
        raise ValueError(f"unsupported integration mode: {mode}")
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    states = load_states()
    if mode is None:
        states.pop(harness, None)
    else:
        states[harness] = {"mode": mode}
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".integrations.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(states, handle, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)

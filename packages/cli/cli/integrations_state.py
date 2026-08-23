# SPDX-License-Identifier: MIT
"""Persistent consent modes for harness observation integrations.

The four modes are a privacy contract, not a label:

``off``
    no observation spool and no receipt upload.
``local-only``
    spool and pending list stay on this machine; nothing is uploaded.
``prompt``
    spool locally; every receipt upload asks first.
``auto``
    spool locally; the companion may upload one receipt per completed
    task without asking again.

Receipt-upload consent and review consent are distinct scopes. A harness may
be allowed to collect/upload deterministic receipts while automatic usage
reviews remain off, and vice versa.

``off`` is stored explicitly rather than inferred from a missing entry so
that ``integrations status`` can distinguish "the user declined" from
"never configured", and so a later default change cannot silently
re-enable a harness the user turned off.

An external opt-out always wins: ``DO_NOT_TRACK``/``LOGION_DO_NOT_TRACK``
force ``off`` regardless of what is stored here. Logion never reads the
inverse — an upstream tool's telemetry being *enabled* is not consent for
Logion.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from cli._json import JsonObject, JsonValue, opt_str
from cli._local_state import get_home

OFF = "off"
LOCAL_ONLY = "local-only"
PROMPT = "prompt"
AUTO = "auto"

VALID_MODES = frozenset({OFF, LOCAL_ONLY, PROMPT, AUTO})

#: Modes that permit writing to the local observation spool.
SPOOLING_MODES = frozenset({LOCAL_ONLY, PROMPT, AUTO})

#: Modes that permit a network write. ``prompt`` additionally requires an
#: explicit per-call confirmation at the call site.
UPLOADING_MODES = frozenset({PROMPT, AUTO})
REVIEW_MODES = frozenset({OFF, AUTO})

_DNT_DISABLED_VALUES = frozenset({"", "0", "false", "no", "off"})


def _path() -> Path:
    return get_home() / "integrations.json"


def do_not_track() -> bool:
    """True if the environment carries a global tracking opt-out."""
    for name in ("LOGION_DO_NOT_TRACK", "DO_NOT_TRACK"):
        value = os.environ.get(name)
        if value is not None and value.strip().lower() not in (
            _DNT_DISABLED_VALUES
        ):
            return True
    return False


def load_states() -> dict[str, JsonObject]:
    path = _path()
    if not path.is_file() or path.is_symlink():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        key: value for key, value in data.items() if isinstance(value, dict)
    }


def get_mode(harness: str) -> str | None:
    """The stored mode, or ``None`` when the harness was never configured."""
    state = load_states().get(harness) or {}
    mode = opt_str(state, "mode")
    return mode if mode in VALID_MODES else None


def get_review_mode(harness: str) -> str | None:
    """The stored review scope, or ``None`` when never configured."""
    state = load_states().get(harness) or {}
    mode = opt_str(state, "review_mode")
    return mode if mode in REVIEW_MODES else None


def effective_mode(harness: str) -> str:
    """The mode actually in force, after external opt-out and defaults.

    An unconfigured harness is ``off``: observation is opt-in.
    """
    if do_not_track():
        return OFF
    return get_mode(harness) or OFF


def effective_review_mode(harness: str) -> str:
    """The review scope actually in force after external opt-out."""
    if do_not_track():
        return OFF
    return get_review_mode(harness) or OFF


def may_spool(harness: str) -> bool:
    """True if this harness may append to the local observation spool."""
    return effective_mode(harness) in SPOOLING_MODES


def may_upload(harness: str) -> bool:
    """True if this harness may upload deterministic receipts."""
    return effective_mode(harness) in UPLOADING_MODES


def may_auto_review(harness: str) -> bool:
    """True if this harness may auto-submit usage reviews."""
    return effective_review_mode(harness) == AUTO


def set_mode(harness: str, mode: str | None) -> None:
    if mode is not None and mode not in VALID_MODES:
        raise ValueError(f"unsupported integration mode: {mode}")
    states = load_states()
    if mode is None:
        states.pop(harness, None)
    else:
        existing = states.get(harness) or {}
        existing["mode"] = mode
        states[harness] = existing
    _write_states(states)


def set_review_mode(harness: str, mode: str | None) -> None:
    if mode is not None and mode not in REVIEW_MODES:
        raise ValueError(f"unsupported review mode: {mode}")
    states = load_states()
    if mode is None:
        state = states.get(harness)
        if state is None:
            return
        state.pop("review_mode", None)
        if state:
            states[harness] = state
        else:
            states.pop(harness, None)
    else:
        existing = states.get(harness) or {}
        existing["review_mode"] = mode
        states[harness] = existing
    _write_states(states)


def managed_hooks(harness: str) -> list[JsonObject]:
    """Hook entries Logion installed for *harness*, newest last.

    Recorded on Logion's side of the fence rather than as a custom key
    inside the harness's own config: the harnesses validate their hook
    entries, and an unrecognized field there could break the user's
    agent. Uninstall matches on this record plus the command it names.
    """
    state = load_states().get(harness) or {}
    hooks = state.get("managed_hooks")
    if not isinstance(hooks, list):
        return []
    return [entry for entry in hooks if isinstance(entry, dict)]


def record_managed_hook(
    harness: str, *, config_path: str, scope: str, command: str
) -> None:
    """Remember that Logion owns one hook entry in *config_path*."""
    states = load_states()
    state = states.get(harness) or {}
    entries = [
        entry
        for entry in managed_hooks(harness)
        if entry.get("config_path") != config_path
    ]
    entry: JsonObject = {
        "config_path": config_path,
        "scope": scope,
        "command": command,
    }
    entries.append(entry)
    values: list[JsonValue] = list(entries)
    state["managed_hooks"] = values
    states[harness] = state
    _write_states(states)


def forget_managed_hook(harness: str, *, config_path: str) -> None:
    """Drop the record for one config file after removing its hook."""
    states = load_states()
    state = states.get(harness) or {}
    remaining: list[JsonValue] = [
        entry
        for entry in managed_hooks(harness)
        if entry.get("config_path") != config_path
    ]
    state["managed_hooks"] = remaining
    states[harness] = state
    _write_states(states)


def _write_states(states: dict[str, JsonObject]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
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

# SPDX-License-Identifier: MIT
"""Resolve a raw harness hook payload to a local installation.

A harness hook knows paths; the observation spool must never contain
one.  This module is the boundary between the two: it reads the native
``PostToolUse`` payload, matches the paths it carries against the local
acquisition receipts, and returns the opaque installation identity.  The
paths themselves stay in memory and are dropped when the call returns.

Attribution is deliberately conservative.  Only arguments that *are* a
path are considered — never the session's ``cwd``, because "a tool ran
somewhere inside this repository" is not evidence that an installed
resource was used.  When one path is inside two installations the most
specific one wins; when two receipts are equally specific the event is
dropped rather than guessed.
"""

from __future__ import annotations

import hmac
import os
import re
from pathlib import Path

from cli._json import JsonObject, JsonValue, opt_str
from cli._local_state import get_home
from cli._receipts import load_receipts

#: ``tool_input`` keys that hold a filesystem path across the harnesses
#: whose hook payloads are pinned in ``tests/fixtures/hook_payloads/``.
PATH_ARGUMENT_KEYS: tuple[str, ...] = (
    "file_path",
    "filePath",
    "path",
    "notebook_path",
    "notebookPath",
)

#: Keys holding a shell command line, scanned for path-shaped tokens.
COMMAND_ARGUMENT_KEYS: tuple[str, ...] = ("command",)

#: A token in a command line is only treated as a path when it contains a
#: separator. A bare word like ``pytest`` is a program name, not evidence.
_PATH_TOKEN_RE = re.compile(r"[^\s'\"|;&><]*/[^\s'\"|;&><]*")


def session_hash_for(session_id: str) -> str:
    """Opaque, profile-scoped digest of a harness session id.

    The raw ``session_id`` is a harness-side correlation key; hashing it
    with the local home as the HMAC key keeps grouping working without
    writing an identifier that means anything off this machine.
    """
    key = str(get_home()).encode("utf-8")
    message = f"logion.session.v1\0{session_id}".encode()
    return hmac.new(key, message, "sha256").hexdigest()[:32]


def _normalize(raw: str) -> Path | None:
    """Best-effort absolute path for *raw*, or ``None`` if unusable."""
    text = raw.strip().strip("'\"")
    if not text:
        return None
    try:
        expanded = Path(text).expanduser()
        return Path(os.path.normpath(expanded.absolute()))
    except (OSError, RuntimeError, ValueError):
        return None


def _command_tokens(command: str) -> list[str]:
    """Path-shaped tokens inside a shell command line."""
    return [match.group(0) for match in _PATH_TOKEN_RE.finditer(command)]


def candidate_paths(payload: JsonObject) -> list[Path]:
    """Absolute paths a hook payload names as tool arguments.

    Returns an empty list for payloads that carry no path argument —
    which is the common case and must stay silent, not become a guess.
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    found: list[Path] = []
    for key in PATH_ARGUMENT_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str):
            normalized = _normalize(value)
            if normalized is not None:
                found.append(normalized)
    for key in COMMAND_ARGUMENT_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str):
            for token in _command_tokens(value):
                normalized = _normalize(token)
                if normalized is not None:
                    found.append(normalized)
    return found


def _target_path(receipt: JsonObject) -> Path | None:
    raw = opt_str(receipt, "target_path")
    if not raw:
        return None
    return _normalize(raw)


def _receipt_paths(receipt: JsonObject) -> list[Path]:
    """Concrete filesystem paths a receipt says belong to one installation.

    ``target_path`` is the historical primary location, but delegated native
    managers can also report a fuller ``installed_paths`` list. Attribution
    should accept any of those explicit paths rather than assuming the first
    one is the only path a harness may reference.
    """
    paths: list[Path] = []
    target = _target_path(receipt)
    if target is not None:
        paths.append(target)
    base = target.parent if target is not None else None
    installed = receipt.get("installed_paths")
    if isinstance(installed, list):
        for item in installed:
            if not isinstance(item, str):
                continue
            candidate = _normalize(item)
            if candidate is None and base is not None:
                candidate = _normalize(str(base / item))
            if candidate is not None:
                paths.append(candidate)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _covers(target: Path, candidate: Path) -> bool:
    if candidate == target:
        return True
    return target in candidate.parents


def resolve_installations(
    payload: JsonObject,
    *,
    receipts: list[JsonObject] | None = None,
) -> list[JsonObject]:
    """Receipts whose installed tree contains a path named by *payload*.

    One receipt per distinct installation, so a payload touching two
    resources produces two observations rather than one arbitrary
    winner. A single path nested in two installations resolves to the
    longest ``target_path``; an exact tie is dropped.
    """
    inventory = load_receipts() if receipts is None else receipts
    targets = [
        (target, receipt)
        for receipt in inventory
        for target in _receipt_paths(receipt)
    ]
    matched: dict[str, JsonObject] = {}
    for candidate in candidate_paths(payload):
        covering = [
            (target, receipt)
            for target, receipt in targets
            if _covers(target, candidate)
        ]
        if not covering:
            continue
        deepest = max(len(target.parts) for target, _ in covering)
        finalists = [
            receipt
            for target, receipt in covering
            if len(target.parts) == deepest
        ]
        if len(finalists) != 1:
            # Two installations claim the same path with equal
            # specificity: ambiguous, so record nothing.
            continue
        receipt = finalists[0]
        installation_id = opt_str(receipt, "installation_id", "")
        if installation_id:
            matched[installation_id] = receipt
    return list(matched.values())


def receipt_by_installation_id(
    installation_id: JsonValue,
    *,
    receipts: list[JsonObject] | None = None,
) -> JsonObject:
    """Look up the single receipt for an explicitly reported installation.

    Used by companions that already know the installation identity and
    therefore never hand Logion a path at all.
    """
    if not isinstance(installation_id, str) or not installation_id:
        raise ValueError("installation_id is required")
    inventory = load_receipts() if receipts is None else receipts
    matches = [
        receipt
        for receipt in inventory
        if receipt.get("installation_id") == installation_id
    ]
    if len(matches) != 1:
        raise ValueError(
            "installation_id is not uniquely attributed in local inventory"
        )
    return matches[0]


__all__ = [
    "candidate_paths",
    "receipt_by_installation_id",
    "resolve_installations",
    "session_hash_for",
]

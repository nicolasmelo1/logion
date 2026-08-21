# SPDX-License-Identifier: MIT
"""Idempotent merge of the Logion observation hook into a harness config.

Claude Code and Codex both express lifecycle hooks as the same JSON
shape — a ``hooks`` object keyed by event name, each event holding
matcher groups, each group holding command entries::

    {"hooks": {"PostToolUse": [
        {"matcher": "...", "hooks": [{"type": "command", "command": "..."}]}
    ]}}

Sources, verified 2026-08-17:
``https://code.claude.com/docs/en/hooks`` and
``https://learn.chatgpt.com/docs/hooks``.

The merge is conservative on purpose. It preserves every key it does not
own, refuses to edit a file it cannot parse, and removes only entries
whose command is Logion's own — the harnesses validate hook entries, so
stamping a custom marker key inside one risks breaking the user's agent.
Ownership is recorded on Logion's side, in
:mod:`cli.integrations_state`.
"""

from __future__ import annotations

import json
from pathlib import Path

from cli._harness.base import (
    OBSERVATION_COMMAND,
    HarnessConfigError,
    ObservationPlan,
)
from cli._harness.scopes import canonical_scope
from cli._json import JsonObject, JsonValue
from cli._local_state import _atomic_write_text

POST_TOOL_USE = "PostToolUse"

#: Seconds before the harness cancels the hook. ``usage observe`` targets
#: well under this; the margin is for a cold interpreter start.
HOOK_TIMEOUT_SECONDS = 10

_COMMAND_PREFIX = " ".join(OBSERVATION_COMMAND)


def is_logion_hook(entry: JsonValue) -> bool:
    """True if *entry* is a hook command Logion installed."""
    if not isinstance(entry, dict):
        return False
    command = entry.get("command")
    return isinstance(command, str) and command.startswith(_COMMAND_PREFIX)


def _event_groups(settings: JsonObject, path: str) -> list[JsonValue]:
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise HarnessConfigError(
            f"{path}: 'hooks' is not an object — refusing to edit"
        )
    groups = hooks.setdefault(POST_TOOL_USE, [])
    if not isinstance(groups, list):
        raise HarnessConfigError(
            f"{path}: 'hooks.{POST_TOOL_USE}' is not a list — refusing to edit"
        )
    return groups


def has_observation_hook(settings: JsonObject) -> bool:
    """True if the config already carries the Logion observation hook."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    groups = hooks.get(POST_TOOL_USE)
    if not isinstance(groups, list):
        return False
    for group in groups:
        if not isinstance(group, dict):
            continue
        entries = group.get("hooks")
        if isinstance(entries, list) and any(
            is_logion_hook(entry) for entry in entries
        ):
            return True
    return False


def _set_logion_hook_async(
    settings: JsonObject, *, asynchronous: bool
) -> bool:
    """Migrate existing Logion hooks to the requested execution mode."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    groups = hooks.get(POST_TOOL_USE)
    if not isinstance(groups, list):
        return False
    changed = False
    for group in groups:
        if not isinstance(group, dict):
            continue
        entries = group.get("hooks")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not is_logion_hook(entry):
                continue
            if asynchronous:
                if entry.get("async") is not True:
                    entry["async"] = True
                    changed = True
            elif "async" in entry:
                entry.pop("async")
                changed = True
    return changed


def add_observation_hook(
    settings: JsonObject,
    *,
    path: str,
    matcher: str,
    command: str,
    asynchronous: bool = True,
) -> bool:
    """Add the hook if absent.  Returns True when the config changed."""
    if has_observation_hook(settings):
        return _set_logion_hook_async(settings, asynchronous=asynchronous)
    groups = _event_groups(settings, path)
    entry: JsonObject = {
        "type": "command",
        "command": command,
        "timeout": HOOK_TIMEOUT_SECONDS,
    }
    # Codex v0.147 treats the presence of `async`, even when false, as an
    # async hook and skips it. Omit the field for synchronous hooks.
    if asynchronous:
        entry["async"] = True
    groups.append({"matcher": matcher, "hooks": [entry]})
    return True


def remove_observation_hook(settings: JsonObject) -> bool:
    """Strip Logion-owned hook entries.  Returns True when it changed.

    Groups that held only the Logion entry are dropped; a group the user
    also put their own hook in keeps that hook and its matcher.
    """
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    groups = hooks.get(POST_TOOL_USE)
    if not isinstance(groups, list):
        return False
    changed = False
    kept_groups: list[JsonValue] = []
    for group in groups:
        if not isinstance(group, dict):
            kept_groups.append(group)
            continue
        entries = group.get("hooks")
        if not isinstance(entries, list):
            kept_groups.append(group)
            continue
        kept_entries = [
            entry for entry in entries if not is_logion_hook(entry)
        ]
        if len(kept_entries) == len(entries):
            kept_groups.append(group)
            continue
        changed = True
        if kept_entries:
            group["hooks"] = kept_entries
            kept_groups.append(group)
    if not changed:
        return False
    if kept_groups:
        hooks[POST_TOOL_USE] = kept_groups
    else:
        hooks.pop(POST_TOOL_USE, None)
    if hooks:
        settings["hooks"] = hooks
    else:
        settings.pop("hooks", None)
    return True


def _render(settings: JsonObject) -> str:
    return json.dumps(settings, indent=2, ensure_ascii=False) + "\n"


def _read(path: Path) -> tuple[JsonObject, str]:
    """Parsed config plus its exact current text (empty when absent)."""
    if not path.is_file():
        return {}, ""
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessConfigError(
            f"cannot parse {path} — refusing to overwrite: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise HarnessConfigError(
            f"{path} is not a JSON object — refusing to overwrite"
        )
    return raw, text


def apply_observation_hook(
    *,
    harness: str,
    scope: str,
    path: Path,
    matcher: str,
    command: str,
    asynchronous: bool = True,
    remove: bool = False,
    dry_run: bool = False,
) -> ObservationPlan:
    """Merge or strip the Logion hook in a JSON hooks config.

    With ``dry_run`` nothing is written and the returned plan still
    carries the diff the write would have produced.
    """
    settings, before = _read(path)
    if remove:
        changed = remove_observation_hook(settings)
    else:
        changed = add_observation_hook(
            settings,
            path=str(path),
            matcher=matcher,
            command=command,
            asynchronous=asynchronous,
        )
    after = _render(settings) if changed else before
    if changed and not dry_run:
        _atomic_write_text(path, after)
    return ObservationPlan(
        harness=harness,
        scope=canonical_scope(scope),
        supported=True,
        path=path,
        already=not changed,
        changed=changed and not dry_run,
        before=before,
        after=after,
    )


__all__ = [
    "HOOK_TIMEOUT_SECONDS",
    "POST_TOOL_USE",
    "add_observation_hook",
    "apply_observation_hook",
    "has_observation_hook",
    "is_logion_hook",
    "remove_observation_hook",
]

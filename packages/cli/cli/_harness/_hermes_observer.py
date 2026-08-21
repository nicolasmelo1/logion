# SPDX-License-Identifier: MIT
"""Source template for Logion's Hermes lifecycle observer.

The generated plugin is deliberately stdlib-only. It observes only named skill
loads, derives the candidate skill directory locally, and hands that transient
path to the Logion CLI for receipt-backed attribution. Neither the plugin nor
the Logion spool persists prompts, arguments, paths, or raw session ids.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

_PLUGIN_NAME = "logion-observer"
_SAFE_SKILL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class PluginContext(Protocol):
    """The only Hermes plugin API surface this observer requires."""

    def register_hook(self, name: str, _: Callable[..., None]) -> object: ...


def _hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME")
    return (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".hermes"
    )


def _payload(kwargs: dict[str, object]) -> bytes | None:
    """Build the only transient payload accepted by ``usage observe``."""
    if kwargs.get("action") != "loaded":
        return None
    skill_name = kwargs.get("skill_name")
    if not isinstance(skill_name, str) or not _SAFE_SKILL_NAME.fullmatch(
        skill_name
    ):
        return None
    session_id = kwargs.get("session_id")
    data: dict[str, object] = {
        "event": "resource_invoked",
        "tool_input": {"path": str(_hermes_home() / "skills" / skill_name)},
    }
    if isinstance(session_id, str) and session_id:
        data["session_id"] = session_id
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


def on_skill_lifecycle(**kwargs: object) -> None:
    """Send a bounded, fail-open lifecycle signal to the local CLI."""
    try:
        payload = _payload(kwargs)
        if payload is None:
            return
        with contextlib.suppress(
            FileNotFoundError, OSError, subprocess.TimeoutExpired
        ):
            subprocess.run(
                [
                    "logion",
                    "usage",
                    "observe",
                    "--harness",
                    "hermes",
                    "--stdin",
                ],
                input=payload,
                timeout=2,
                check=False,
                capture_output=True,
            )
    except Exception:
        return


def register(ctx: PluginContext) -> None:
    """Register only the pinned named-skill lifecycle hook."""
    ctx.register_hook("on_skill_lifecycle", on_skill_lifecycle)

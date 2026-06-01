# SPDX-License-Identifier: MIT
"""Minimal .env loader.

Reads ``KEY=value`` lines and merges them into ``os.environ`` without
taking a new dependency.  Existing ``os.environ`` entries win, so an
explicit shell variable always beats the ``.env`` default.  Picks up
``HF_TOKEN``, ``LOGION_*`` defaults, and ``DSPY_*`` knobs the optimize
commands forward to the optimizer scripts.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(env_path: Path) -> None:
    """Merge ``KEY=value`` pairs from ``env_path`` into ``os.environ``.

    Silently no-ops when the file does not exist.  Existing
    ``os.environ`` entries are preserved so an explicit shell var
    always beats the ``.env`` default.
    """
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

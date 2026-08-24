# SPDX-License-Identifier: MIT
"""Schema package — static JSON Schema file and loader."""

from __future__ import annotations

import json
from pathlib import Path

from logion_instrumentation._json import JsonValue

_SCHEMA_DIR = Path(__file__).parent
_SCHEMA_FILE = _SCHEMA_DIR / "logion.instrumentation.v1.json"


def schema_path() -> Path:
    """Return the filesystem path to the v1 schema JSON file."""
    return _SCHEMA_FILE


def load_schema() -> dict[str, JsonValue]:
    """Load and return the v1 JSON Schema as a dict."""
    with _SCHEMA_FILE.open(encoding="utf-8") as fh:
        result: dict[str, JsonValue] = json.load(fh)
        return result

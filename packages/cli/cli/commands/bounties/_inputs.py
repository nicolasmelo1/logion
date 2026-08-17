# SPDX-License-Identifier: MIT
"""Argument parsing helpers shared by the bounties handlers."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from cli._errors import print_err
from cli._json import JsonObject


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime string, treating trailing Z as UTC."""
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_evidence(path: Path | None) -> JsonObject | None:
    """Load a JSON evidence file, returning None if *path* is None.

    Returns ``None`` and prints a user-facing error when the file is
    missing, is not valid JSON, or does not hold a JSON object.
    """
    if path is None:
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print_err(f"Error: evidence JSON must be valid: {exc}")
        return None
    if not isinstance(data, dict):
        print_err("Error: evidence JSON must be an object")
        return None
    return data


def parse_bool(value: str) -> bool:
    """Parse a boolean flag string for argparse."""
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "on"}:
        return True
    if lowered in {"false", "0", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value!r}")

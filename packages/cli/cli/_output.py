"""Output helpers — JSON and human-readable formatting."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def to_data(value: Any) -> Any:
    """Recursively convert Pydantic models to plain JSON-safe data."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [to_data(item) for item in value]
    if isinstance(value, dict):
        return {key: to_data(item) for key, item in value.items()}
    return value


def emit(value: Any, *, json_output: bool) -> None:
    """Print *value* as JSON.

    In JSON mode the output is sorted and indented for scripts.
    In human mode the output is indented but preserves natural key order
    for readability.
    """
    data = to_data(value)
    if json_output:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(json.dumps(data, indent=2))

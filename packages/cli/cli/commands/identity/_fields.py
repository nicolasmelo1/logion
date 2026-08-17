# SPDX-License-Identifier: MIT
"""Reading fields off identity responses."""

from __future__ import annotations

from cli._json import JsonValue
from cli._output import to_data


def field(obj: object, name: str) -> JsonValue:
    """Read *name* off a decoded body or an attribute-style response.

    Some identity endpoints hand back an SDK model and some a plain
    mapping, so both are supported. A scalar is returned as-is;
    anything richer goes through ``to_data`` so nested models come back
    as plain JSON.
    """
    value = (
        obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
    )
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return to_data(value)

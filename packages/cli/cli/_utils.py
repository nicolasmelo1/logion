"""CLI utility helpers — generic kwarg building, etc."""

from __future__ import annotations

from typing import Any


def only_not_none(
    base: dict[str, Any],
    **optional: Any,
) -> dict[str, Any]:
    """Return *base* merged with only the non-None *optional* entries."""
    result = dict(base)
    result.update({k: v for k, v in optional.items() if v is not None})
    return result

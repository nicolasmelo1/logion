# SPDX-License-Identifier: MIT
"""Output helpers — JSON and human-readable formatting."""

from __future__ import annotations

import json
from types import SimpleNamespace

from cli._json import JsonObject, JsonValue


def to_data(value: object) -> JsonValue:
    """Recursively convert Pydantic models to plain JSON-safe data.

    Takes ``object`` because callers hand it whatever the SDK returned —
    a model, a namespace, an already-decoded body. It returns
    ``JsonValue``, which is what every caller then either prints through
    ``json.dumps`` or reads fields off.
    """
    if isinstance(value, SimpleNamespace):
        return {key: to_data(val) for key, val in vars(value).items()}
    if isinstance(value, list):
        return [to_data(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_data(item) for key, item in value.items()}
    if value is None or isinstance(value, str | int | float | bool):
        return value

    # Duck-typed rather than isinstance(BaseModel): it keeps pydantic
    # out of this module entirely, which matters because _output is on
    # the parser-setup import path (see test_cli_startup).
    #
    # The result has to be a real mapping to count. Without that check a
    # MagicMock -- which answers every getattr -- would dump to another
    # MagicMock and recurse forever.
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, dict):
            return {str(key): to_data(item) for key, item in dumped.items()}
    # Anything left is not JSON-safe. This used to be returned as-is and
    # blew up inside json.dumps one frame later; raising here says the
    # same thing at the point that actually knows what went wrong.
    msg = f"cannot render {type(value).__name__} as JSON"
    raise TypeError(msg)


def to_object(value: object) -> JsonObject:
    """Convert *value* to JSON-safe data, requiring a JSON object.

    The human-readable renderers all read named fields off a response,
    so they want an object rather than the full JSON grammar. Narrowing
    once here keeps that isinstance check out of every renderer.
    """
    data = to_data(value)
    if not isinstance(data, dict):
        msg = f"expected a JSON object, got {type(data).__name__}"
        raise TypeError(msg)
    return data


def to_items(value: object) -> list[JsonObject]:
    """Convert *value* to the collection of objects it represents.

    Tolerates both encodings the API uses for a collection: a bare
    array, and an object wrapping the array under ``items``. Entries
    that are not objects are skipped, which is what the hand-written
    ``isinstance`` loops this replaces already did.
    """
    data = to_data(value)
    if isinstance(data, dict):
        data = data.get("items")
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def emit_json(kind: str, data: object) -> None:
    """Print a v1 JSON envelope with version, kind, and data."""
    payload: JsonObject = {
        "version": "v1",
        "kind": kind,
        "data": to_data(data),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def truncate_summary(text: str | None, max_len: int = 120) -> str:
    """Truncate *text* to *max_len* chars, appending ``…`` if truncated."""
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def emit(value: object, *, json_output: bool) -> None:
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

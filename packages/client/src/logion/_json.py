# SPDX-License-Identifier: MIT
"""Recursive JSON types and the narrowing helpers that consume them.

``typing.Any`` is banned repo-wide (ruff ``TID251``). At a genuine JSON
boundary — ``json.loads``, an HTTP body, a YAML document — the shape is
not known statically, but it is *not* arbitrary either: it is exactly the
JSON value grammar. ``JsonValue`` says that and nothing more, so callers
must narrow a field before using it.

Prefer a ``TypedDict`` (or a Pydantic model) whenever the shape *is*
known. Reach for ``JsonValue``/``JsonObject`` only where the payload is
genuinely opaque, and use the ``require_*``/``opt_*`` helpers to cross
back into concrete types. They raise :class:`JsonShapeError` with the
offending key and the type actually seen, which is a far better failure
than the ``KeyError``/``TypeError`` an unchecked ``d["field"]`` produces
three frames later.

This module is duplicated verbatim into every publishable package so no
package gains a dependency purely for typing. ``make check-json-module``
(part of ``make ci-checks``) fails if the copies drift.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeAlias

#: Any value the JSON grammar can produce, recursively.
#:
#: The container arms are the *covariant* ``Sequence``/``Mapping`` rather
#: than ``list``/``dict``. ``list`` is invariant, so a plain
#: ``list[JsonValue]`` arm would reject an ordinary ``list[str]`` —
#: forcing a rewrite at every site that builds a payload out of already
#: concrete values. Covariance makes ``{"tags": tags}`` type-check with
#: ``tags: list[str]``, which is the overwhelmingly common case.
JsonValue: TypeAlias = (
    "str | int | float | bool | None"
    " | Sequence[JsonValue] | Mapping[str, JsonValue]"
)

#: A JSON object — the common case for a decoded body or document.
#:
#: Mutable and invariant on purpose: the *outer* container is usually
#: built up key by key, so ``dict`` is what callers want. Only the
#: values nested inside it are covariant.
JsonObject: TypeAlias = "dict[str, JsonValue]"

#: A JSON array — the common case for a decoded list body.
JsonArray: TypeAlias = "list[JsonValue]"

__all__ = [
    "JsonArray",
    "JsonObject",
    "JsonShapeError",
    "JsonValue",
    "as_array",
    "as_object",
    "child",
    "children",
    "opt_bool",
    "opt_int",
    "opt_object",
    "opt_object_array",
    "opt_str",
    "opt_str_array",
    "require_array",
    "require_bool",
    "require_int",
    "require_number",
    "require_object",
    "require_object_array",
    "require_str",
    "require_str_array",
]


class JsonShapeError(ValueError):
    """A decoded JSON value did not have the expected shape."""


def _describe(value: JsonValue) -> str:
    """Return a short, user-facing name for *value*'s JSON type."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _fail(where: str, expected: str, value: JsonValue) -> JsonShapeError:
    """Build the error raised when *where* held the wrong JSON type."""
    return JsonShapeError(
        f"{where}: expected {expected}, got {_describe(value)}"
    )


# ── whole-document narrowing ─────────────────────────────────────


def as_object(value: JsonValue, *, where: str = "document") -> JsonObject:
    """Narrow a decoded value to a JSON object."""
    if isinstance(value, dict):
        return value
    raise _fail(where, "an object", value)


def as_array(value: JsonValue, *, where: str = "document") -> JsonArray:
    """Narrow a decoded value to a JSON array."""
    if isinstance(value, list):
        return value
    raise _fail(where, "an array", value)


# ── required fields ──────────────────────────────────────────────


def require_str(obj: JsonObject, key: str) -> str:
    """Return ``obj[key]`` as a string, or raise."""
    value = obj.get(key)
    if isinstance(value, str):
        return value
    raise _fail(key, "a string", value)


def require_int(obj: JsonObject, key: str) -> int:
    """Return ``obj[key]`` as an integer, or raise.

    Booleans are rejected: ``isinstance(True, int)`` is true in Python,
    but a JSON ``true`` is not an integer field.
    """
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(key, "an integer", value)
    return value


def require_number(obj: JsonObject, key: str) -> float:
    """Return ``obj[key]`` as a float, or raise."""
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _fail(key, "a number", value)
    return float(value)


def require_bool(obj: JsonObject, key: str) -> bool:
    """Return ``obj[key]`` as a boolean, or raise."""
    value = obj.get(key)
    if isinstance(value, bool):
        return value
    raise _fail(key, "a boolean", value)


def require_object(obj: JsonObject, key: str) -> JsonObject:
    """Return ``obj[key]`` as a JSON object, or raise."""
    value = obj.get(key)
    if isinstance(value, dict):
        return value
    raise _fail(key, "an object", value)


def require_array(obj: JsonObject, key: str) -> JsonArray:
    """Return ``obj[key]`` as a JSON array, or raise."""
    value = obj.get(key)
    if isinstance(value, list):
        return value
    raise _fail(key, "an array", value)


def require_str_array(obj: JsonObject, key: str) -> list[str]:
    """Return ``obj[key]`` as an array of strings, or raise."""
    items = require_array(obj, key)
    for index, item in enumerate(items):
        if not isinstance(item, str):
            raise _fail(f"{key}[{index}]", "a string", item)
    return [item for item in items if isinstance(item, str)]


def require_object_array(obj: JsonObject, key: str) -> list[JsonObject]:
    """Return ``obj[key]`` as an array of JSON objects, or raise."""
    items = require_array(obj, key)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise _fail(f"{key}[{index}]", "an object", item)
    return [item for item in items if isinstance(item, dict)]


# ── optional fields ──────────────────────────────────────────────
#
# ``opt_*`` treats a missing key and an explicit ``null`` alike: both
# mean "not provided". A present-but-wrong-typed value still raises,
# so a typo in a payload is never silently swallowed as a default.


def opt_str(
    obj: JsonObject, key: str, default: str | None = None
) -> str | None:
    """Return ``obj[key]`` as a string when present, else *default*."""
    value = obj.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        return value
    raise _fail(key, "a string or null", value)


def opt_int(
    obj: JsonObject, key: str, default: int | None = None
) -> int | None:
    """Return ``obj[key]`` as an integer when present, else *default*."""
    value = obj.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(key, "an integer or null", value)
    return value


def opt_bool(
    obj: JsonObject, key: str, default: bool | None = None
) -> bool | None:
    """Return ``obj[key]`` as a boolean when present, else *default*."""
    value = obj.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise _fail(key, "a boolean or null", value)


def opt_object(obj: JsonObject, key: str) -> JsonObject | None:
    """Return ``obj[key]`` as a JSON object when present, else ``None``."""
    value = obj.get(key)
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    raise _fail(key, "an object or null", value)


def child(obj: JsonObject, key: str) -> JsonObject:
    """Return the nested object at *key*, or an empty one.

    This is the typed replacement for a ``.get(key, {})`` traversal
    chain over a document whose branches are all optional — a config
    file, an OpenAPI spec, a CMS-style content tree. Unlike
    :func:`opt_object` it never raises, so a branch of the wrong type
    reads as absent; use it only where that is the intent.
    """
    value = obj.get(key)
    return value if isinstance(value, dict) else {}


def children(obj: JsonObject, key: str) -> list[JsonObject]:
    """Return the objects in the array at *key*, skipping the rest.

    The array counterpart of :func:`child`, with the same forgiving
    contract: a missing key, a non-array, or a non-object entry is
    skipped rather than raised on. Use :func:`require_object_array`
    when a malformed entry should be an error instead.
    """
    value = obj.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def opt_str_array(obj: JsonObject, key: str) -> list[str]:
    """Return ``obj[key]`` as an array of strings, empty when absent."""
    if obj.get(key) is None:
        return []
    return require_str_array(obj, key)


def opt_object_array(obj: JsonObject, key: str) -> list[JsonObject]:
    """Return ``obj[key]`` as an array of objects, empty when absent."""
    if obj.get(key) is None:
        return []
    return require_object_array(obj, key)

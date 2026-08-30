"""JCS-style canonical JSON (RFC 8785 subset).

The coordinator and every receipt verifier must serialize a receipt to
*identical bytes* before hashing or signing. This module implements the
canonicalization both sides agree on:

Algorithm
---------

1. **Objects**: keys are sorted recursively by Unicode code point
   (``sorted`` on the Python ``str`` compares code points) and emitted
   with no whitespace between tokens. Duplicate keys cannot occur in a
   Python dict, so no duplicate-key resolution is needed.
2. **Strings**: emitted as UTF-8 with ``ensure_ascii=False``; only the
   two mandatory escapes (``"`` and ``\\``) plus the C0 control range
   are escaped, using the JSON short escape when one exists.
3. **Numbers**: integers pass through; floats use Python's shortest
   round-trip representation (``repr``), which matches the ECMAScript
   ``Number::toString`` behaviour JCS requires on these digests.
4. **Arrays**: values in order, comma-separated. Order is significant
   and never sorted.
5. **null / booleans**: ``null``, ``true``, ``false`` literally.

The result is UTF-8 encoded; callers sign or hash those bytes and never
a re-serialization of them.
"""

from __future__ import annotations

import json
import math

from logion_runner._json import JsonValue

_STRING_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _escape_string(value: str) -> str:
    out: list[str] = ['"']
    for char in value:
        escape = _STRING_ESCAPES.get(char)
        if escape is not None:
            out.append(escape)
        elif char < " ":
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _format_number(value: float) -> str:
    """Shortest round-trip form; JCS forbids NaN/Infinity."""
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"cannot canonicalize non-finite number: {value!r}")
    if value == 0:
        return "0"
    if value.is_integer() and abs(value) < 1e21:
        # A float that is a whole number canonicalizes without a
        # trailing ".0": JCS emits the integer form.
        return str(int(value))
    return repr(value)


def _canonical(value: JsonValue, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif isinstance(value, bool):
        out.append("true" if value else "false")
    elif isinstance(value, int):
        out.append(str(value))
    elif isinstance(value, float):
        out.append(_format_number(value))
    elif isinstance(value, str):
        out.append(_escape_string(value))
    elif isinstance(value, list):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _canonical(item, out)
        out.append("]")
    elif isinstance(value, dict):
        out.append("{")
        for index, key in enumerate(sorted(value)):
            if index:
                out.append(",")
            out.append(_escape_string(key))
            out.append(":")
            _canonical(value[key], out)
        out.append("}")
    else:
        raise TypeError(
            f"cannot canonicalize non-JSON value of type {type(value)!r}"
        )


def canonicalize(value: JsonValue) -> bytes:
    """Return the JCS-canonical UTF-8 encoding of *value*."""
    out: list[str] = []
    _canonical(value, out)
    return "".join(out).encode("utf-8")


def canonicalize_text(value: JsonValue) -> str:
    """Convenience: canonical form as a str (for display/inspection)."""
    return canonicalize(value).decode("utf-8")


def short_sha256(value: JsonValue) -> str:
    """SHA-256 hex digest over the canonical bytes."""
    import hashlib

    return hashlib.sha256(canonicalize(value)).hexdigest()


# Self-check: parsing the canonical text yields the same value, so
# canonicalize(json.loads(text)) is stable (idempotent).
def is_round_trip_stable(value: JsonValue) -> bool:
    """True when canonicalizing the parsed canonical text is a fixpoint."""
    text = canonicalize(value).decode("utf-8")
    reparsed: JsonValue = json.loads(text)
    return canonicalize(reparsed) == canonicalize(value)

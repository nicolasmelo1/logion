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
from decimal import Decimal

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
    """Format using the ECMAScript number form required by RFC 8785."""
    if not math.isfinite(value):
        raise ValueError(f"cannot canonicalize non-finite number: {value!r}")
    if value == 0:
        return "0"
    text = repr(value).lower()
    if "e" not in text:
        if text.endswith(".0"):
            text = text[:-2]
        return text
    mantissa, exponent_text = text.split("e")
    exponent = int(exponent_text)
    digits = mantissa.replace(".", "").lstrip("+")
    sign = ""
    if digits.startswith("-"):
        sign, digits = "-", digits[1:]
    if exponent >= -6 and exponent < 21:
        expanded = format(Decimal(text), "f")
        if "." in expanded:
            expanded = expanded.rstrip("0").rstrip(".")
        return expanded
    normalized = digits[0] + ("." + digits[1:] if len(digits) > 1 else "")
    return f"{sign}{normalized}e{'+' if exponent >= 0 else ''}{exponent}"


def _canonical_scalar(value: JsonValue) -> str | None:
    """The canonical form of a scalar, or ``None`` if it is a container.

    ``bool`` is tested before ``int`` because ``bool`` subclasses ``int``
    in Python, and ``True`` must serialize as ``true``, never ``1``.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _format_number(value)
    if isinstance(value, str):
        return _escape_string(value)
    return None


def _canonical_array(value: list, out: list[str]) -> None:
    out.append("[")
    for index, item in enumerate(value):
        if index:
            out.append(",")
        _canonical(item, out)
    out.append("]")


def _canonical_object(value: dict, out: list[str]) -> None:
    out.append("{")
    for index, key in enumerate(sorted(value)):
        if index:
            out.append(",")
        out.append(_escape_string(key))
        out.append(":")
        _canonical(value[key], out)
    out.append("}")


def _canonical(value: JsonValue, out: list[str]) -> None:
    scalar = _canonical_scalar(value)
    if scalar is not None:
        out.append(scalar)
    elif isinstance(value, list):
        _canonical_array(value, out)
    elif isinstance(value, dict):
        _canonical_object(value, out)
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

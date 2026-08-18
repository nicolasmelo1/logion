# SPDX-License-Identifier: MIT
"""Rewrite ``Any`` out of the datamodel-codegen output.

An OpenAPI property declared as a free-form ``{"type": "object"}``
becomes ``dict[str, Any]`` in the generated models. That is the right
*shape* — the contract really does say "some JSON object here" — but
``Any`` is banned repo-wide, and it is also less precise than what we
can say: the value is JSON, not anything at all.

This runs as the last step of both ``generate-models`` and
``check-models``, so the checked-in file and the freshly generated one
stay byte-identical.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

IMPORT_RE = re.compile(r"^from typing import (.+)$", re.MULTILINE)
JSON_IMPORT = "from logion._json import JsonObject, JsonValue\n"

# When the OpenAPI contract names free-form object schemas (JsonObject-Input,
# JsonObject-Output, JsonValue-Input, JsonValue-Output), datamodel-codegen
# emits standalone RootModel classes for them.  Those classes are recursive
# (``list["JsonValueInput" | None]``) and fail at runtime under
# ``from __future__ import annotations`` because ``str | None`` is not
# evaluated lazily inside ``RootModel[...]``.  They are also redundant: the
# canonical types from ``logion._json`` cover the same shape.
#
# The regex matches the full class body (indented lines) up to the next
# blank line.  We use a non-greedy match on the RootModel parameter to
# handle multi-line generics.
JSON_CLASS_RE = re.compile(
    r"^class (JsonValueInput|JsonValueOutput|JsonObjectInput|JsonObjectOutput)"
    r"\([\s\S]*?\):\n(?:    .*\n)+\n",
    re.MULTILINE,
)

# Map the generated class names to the canonical types from ``logion._json``.
JSON_NAME_MAP = {
    "JsonValueInput": "JsonValue",
    "JsonValueOutput": "JsonValue",
    "JsonObjectInput": "JsonObject",
    "JsonObjectOutput": "JsonObject",
}


def rewrite(source: str) -> str:
    """Return *source* with ``Any`` and JSON RootModel classes replaced."""
    # First handle the legacy ``Any`` path (free-form objects without
    # named schemas).
    if "Any" in source:
        text = source.replace("list[dict[str, Any]]", "list[JsonObject]")
        text = text.replace("dict[str, Any]", "JsonObject")
        text = re.sub(r"(?<![\w.])Any(?![\w\]])", "JsonValue", text)

        def drop_any(match: re.Match[str]) -> str:
            names = [
                name.strip()
                for name in match.group(1).split(",")
                if name.strip() not in {"Any", "JsonValue"}
            ]
            return f"from typing import {', '.join(names)}" if names else ""

        text = IMPORT_RE.sub(drop_any, text, count=1)
    else:
        text = source

    # Remove standalone JSON RootModel class definitions and replace
    # references with canonical types from logion._json.
    # Do this BEFORE the ``Any`` rewrite, so the class names still match.
    has_json_classes = any(name in text for name in JSON_NAME_MAP)
    if has_json_classes:
        # Remove class definitions (multiple passes for adjacent classes).
        for _ in range(4):
            new_text = JSON_CLASS_RE.sub("", text)
            if new_text == text:
                break
            text = new_text
        # Replace remaining type references.
        for gen_name, canon_name in JSON_NAME_MAP.items():
            text = re.sub(
                r"(?<![\w.])" + re.escape(gen_name) + r"(?![\w])",
                canon_name,
                text,
            )
        # Remove orphaned ``model_rebuild()`` calls for removed classes.
        # After replacement, these become ``JsonValue.model_rebuild()`` or
        # ``JsonObject.model_rebuild()`` — but the canonical types from
        # ``logion._json`` are type aliases, not Pydantic models, so they
        # have no ``model_rebuild``.  Drop any line that calls
        # ``model_rebuild`` on a name in JSON_NAME_MAP.values().
        for canon_name in set(JSON_NAME_MAP.values()):
            text = re.sub(
                r"^" + re.escape(canon_name) + r"\.model_rebuild\(\)\n",
                "",
                text,
                flags=re.MULTILINE,
            )

    # Place the alias import after the pydantic block datamodel-codegen
    # emits. That block is parenthesised once it has enough names, so
    # match both forms rather than the opening line alone.
    anchor = re.search(
        r"^from pydantic import (?:\([^)]*\)|[^\n(]+)$",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if anchor is None:
        return text
    end = anchor.end() + 1

    # Only add the import if it's not already there.
    if JSON_IMPORT.strip() not in text:
        return text[:end] + JSON_IMPORT + text[end:]
    return text


def main() -> int:
    """Rewrite the file named on the command line, in place."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    original = args.path.read_text()
    updated = rewrite(original)
    if updated != original:
        args.path.write_text(updated)
    return 0


if __name__ == "__main__":
    sys.exit(main())

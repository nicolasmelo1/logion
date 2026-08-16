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


def rewrite(source: str) -> str:
    """Return *source* with the generated ``Any`` uses replaced."""
    if "Any" not in source:
        return source

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
    return text[:end] + JSON_IMPORT + text[end:]


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

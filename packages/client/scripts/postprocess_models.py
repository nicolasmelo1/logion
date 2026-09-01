# SPDX-License-Identifier: MIT
"""Reconcile the datamodel-codegen output with the contract.

Two jobs. The first rewrites ``Any`` out of the generated models. The
second restores ``additionalProperties: false`` on request bodies, which
``--allow-extra-fields`` erases.

On ``Any``: an OpenAPI property declared as a free-form ``{"type": "object"}``
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
import json
import re
import sys
from pathlib import Path

IMPORT_RE = re.compile(r"^from typing import (.+)$", re.MULTILINE)
JSON_IMPORT = "from logion._json import JsonObject, JsonValue\n"

# datamodel-codegen emits standalone RootModel classes for the contract's
# free-form object schemas. They are recursive
# (``list["JsonValueInput" | None]``) and fail at runtime under
# ``from __future__ import annotations``, because ``str | None`` is not
# evaluated lazily inside ``RootModel[...]`` — and redundant besides, since
# ``logion._json`` already covers the shape.
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


def _closed_request_models(spec_path: Path) -> set[str]:
    """Names of request-body schemas the contract declares closed.

    Only request bodies. A generated *response* model stays permissive on
    purpose: the server may add a field, and a client that refuses one is a
    client that breaks on a compatible change. A request model is the
    opposite case. The server rejects the unknown field either way, so
    mirroring the contract turns a remote 422 into a local error, and stops
    the generated client from reading as a second, softer statement of the
    contract.
    """
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    schemas = spec.get("components", {}).get("schemas", {})
    closed: set[str] = set()
    for operations in spec.get("paths", {}).values():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            body = operation.get("requestBody") or {}
            for media in (body.get("content") or {}).values():
                ref = (media.get("schema") or {}).get("$ref", "")
                if not ref.startswith("#/components/schemas/"):
                    continue
                name = ref.rsplit("/", 1)[1]
                if schemas.get(name, {}).get("additionalProperties") is False:
                    closed.add(name)
    return closed


def forbid_extra(source: str, models: set[str]) -> str:
    """Set ``extra="forbid"`` on each class in *models*."""
    text = source
    for name in sorted(models):
        # Runs before ``ruff format``, so the generator's quote style is
        # whatever datamodel-codegen emitted. Match either.
        #
        # ``--use-schema-description`` puts the schema's description in a
        # class docstring, so ``model_config`` is not always the first line
        # of the body. Skip intervening lines, but never past the start of
        # the next class: without that guard a model whose ``model_config``
        # is missing would quietly match the *following* class and report a
        # successful rewrite of the wrong model.
        pattern = re.compile(
            rf"(class {re.escape(name)}\(BaseModel\):\n"
            rf"(?:(?!class )[^\n]*\n)*?"
            rf"    model_config = ConfigDict\(\n        extra=(['\"]))"
            rf"allow(\2,)"
        )
        text, count = pattern.subn(r"\1forbid\3", text)
        if count != 1:
            raise SystemExit(
                f"postprocess_models: expected one extra='allow' block for "
                f"{name}, found {count}. The generator output changed shape."
            )
    return text


def rewrite(source: str) -> str:
    """Return *source* with ``Any`` and JSON RootModel classes replaced."""
    # First handle the legacy ``Any`` path (free-form objects without
    # named schemas).
    if "Any" in source:
        text = source.replace("list[dict[str, Any]]", "list[JsonObject]")
        text = text.replace("dict[str, Any]", "JsonObject")
        text = re.sub(r"(?<![\w.])Any(?![\w])", "JsonValue", text)

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
    parser.add_argument(
        "--spec",
        type=Path,
        required=True,
        help="OpenAPI contract the models were generated from.",
    )
    args = parser.parse_args()

    original = args.path.read_text()
    closed = _closed_request_models(args.spec)
    updated = forbid_extra(rewrite(original), closed)
    if updated != original:
        args.path.write_text(updated)
    return 0


if __name__ == "__main__":
    sys.exit(main())

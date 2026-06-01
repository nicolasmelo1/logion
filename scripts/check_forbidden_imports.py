#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Forbid imports of SDK internals from outside the SDK package.

Internal modules carry a leading underscore by convention and are
considered private:

  - ``logion.v1._internal``        — HTTP client / token plumbing
  - ``logion.v1._generated``       — generated operation runners
  - ``logion.v1._resources``       — handwritten resource wrappers
  - ``logion.v1._types.generated`` — generated response/request shapes

The SDK's own source and tests (under ``packages/client/``) can import
them freely. Anything outside the SDK package must go through the
public re-exports on ``logion.v1``.

Transitional violations can be allowlisted in
``scripts/check_forbidden_imports.allowlist`` — one ``path:dotted.name``
entry per line with a comment justifying it.
"""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALLOWLIST_PATH = os.path.join(
    ROOT, "scripts", "check_forbidden_imports.allowlist"
)

# Scan the whole workspace except the SDK package itself.
SCAN_DIRS = ("packages",)
SDK_INTERNAL_OK_PREFIX = os.path.join("packages", "client") + os.sep
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

FORBIDDEN_PREFIXES = (
    "logion.v1._internal",
    "logion.v1._generated",
    "logion.v1._resources",
    "logion.v1._types.generated",
)


def load_allowlist() -> set[tuple[str, str]]:
    entries: set[tuple[str, str]] = set()
    if not os.path.isfile(ALLOWLIST_PATH):
        return entries
    with open(ALLOWLIST_PATH) as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split(":", 1)
            if len(parts) == 2:
                entries.add((parts[0].strip(), parts[1].strip()))
    return entries


def is_forbidden(dotted: str) -> bool:
    return any(
        dotted == prefix or dotted.startswith(prefix + ".")
        for prefix in FORBIDDEN_PREFIXES
    )


def scan(path: str) -> list[tuple[int, str]]:
    with open(path) as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return []
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if is_forbidden(node.module):
                hits.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if is_forbidden(alias.name):
                    hits.append((node.lineno, alias.name))
    return hits


def iter_files() -> list[str]:
    files: list[str] = []
    for scan_dir in SCAN_DIRS:
        base = os.path.join(ROOT, scan_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fname in filenames:
                if fname.endswith(".py"):
                    files.append(os.path.join(dirpath, fname))
    return sorted(files)


def main() -> None:
    allowlist = load_allowlist()
    failures: list[tuple[str, int, str]] = []
    for path in iter_files():
        rel = os.path.relpath(path, ROOT)
        # The SDK package can use its own internals freely.
        if rel.startswith(SDK_INTERNAL_OK_PREFIX):
            continue
        for lineno, dotted in scan(path):
            if (rel, dotted) in allowlist:
                continue
            failures.append((rel, lineno, dotted))

    if not failures:
        print("check_forbidden_imports: ok.")
        return

    print("check_forbidden_imports: private-module imports detected:")
    for rel, lineno, dotted in failures:
        print(f"  {rel}:{lineno}  {dotted}")
    print(
        "\nImport via the public surface (`logion.v1.<resource>`) "
        "instead. If a public re-export is missing, add it to the "
        "SDK in a separate PR. To allow a transitional violation, "
        "add `path:dotted.name` to "
        "scripts/check_forbidden_imports.allowlist with a comment."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()

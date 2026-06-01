#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Doc-link liveness check.

Walks every ``.md`` file in the repo and asserts that every
markdown link target ``[text](path)`` either:

  - points at an external URL (``http://``, ``https://``, ``mailto:``),
  - is a pure ``#anchor`` reference, or
  - resolves to a file or directory that actually exists.

This catches the most common LLM doc-hallucination shape: prose that
references a module path or filename that does not exist in the tree.

Allowlist: ``scripts/check_doc_links.allowlist`` — one entry per line,
format ``<md-file-rel-path>:<link-target>``. Use sparingly, e.g. for
links to artifacts produced by a future workflow.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALLOWLIST_PATH = os.path.join(
    ROOT, "scripts", "check_doc_links.allowlist"
)

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

SKIP_DIRS = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "__pycache__",
}

SKIP_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "ftp://",
    "tel:",
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


def is_external(target: str) -> bool:
    if target.startswith(SKIP_PREFIXES):
        return True
    return target.startswith("#")


def walk_markdown_files() -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname.endswith(".md"):
                files.append(os.path.join(dirpath, fname))
    return sorted(files)


def check_file(path: str) -> list[tuple[str, str]]:
    """Return [(target, reason), ...] for broken links in `path`."""
    broken: list[tuple[str, str]] = []
    with open(path) as fh:
        content = fh.read()
    base = os.path.dirname(path)
    for match in LINK_RE.finditer(content):
        raw_target = match.group(1).strip()
        if not raw_target or is_external(raw_target):
            continue
        # Strip in-page anchor.
        target, _ = (
            raw_target.split("#", 1)
            if "#" in raw_target
            else (raw_target, "")
        )
        if not target:
            continue
        resolved = os.path.normpath(os.path.join(base, target))
        if not os.path.exists(resolved):
            broken.append((raw_target, "does not exist"))
    return broken


def main() -> None:
    allowlist = load_allowlist()
    failures: list[tuple[str, str, str]] = []
    for path in walk_markdown_files():
        rel = os.path.relpath(path, ROOT)
        for target, reason in check_file(path):
            if (rel, target) in allowlist:
                continue
            failures.append((rel, target, reason))

    if not failures:
        print("check_doc_links: ok.")
        return

    print("check_doc_links: broken links detected:")
    for rel, target, reason in failures:
        print(f"  {rel}: {target}  [{reason}]")
    print(
        "\nFix the link, or — if it points at something that does "
        "not exist yet — add a `<md-file>:<target>` entry to "
        "scripts/check_doc_links.allowlist with a justification."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()

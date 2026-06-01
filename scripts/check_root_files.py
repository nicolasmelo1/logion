#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail if the repo root contains files or directories not on the
allowlist in ``.allowed-root-files``.

Catches the common AI-PR smell of dropping NOTES.md / PLAN.md /
SUMMARY.md / RESEARCH.md / scratch.py at the root.

Untracked / gitignored entries are ignored (we only check what git
sees). Anything that IS tracked or staged must be allowlisted.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALLOWLIST_PATH = os.path.join(ROOT, ".allowed-root-files")


def load_allowed() -> set[str]:
    allowed: set[str] = set()
    with open(ALLOWLIST_PATH) as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if line:
                allowed.add(line)
    return allowed


def tracked_root_entries() -> set[str]:
    """Names at the repo root that git tracks (top-level only)."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    names: set[str] = set()
    for line in result.stdout.splitlines():
        if not line:
            continue
        # Top-level entry = first path segment.
        names.add(line.split("/", 1)[0])
    return names


def main() -> None:
    allowed = load_allowed()
    present = tracked_root_entries()
    unauthorized = sorted(present - allowed)
    if not unauthorized:
        print("check_root_files: ok.")
        return

    print("check_root_files: unauthorized entries at repo root:")
    for name in unauthorized:
        print(f"  {name}")
    print(
        "\nIf any of these are legitimate, add them to "
        ".allowed-root-files in the same commit. Otherwise move or "
        "delete them. Top-level scratch files are the most common "
        "AI-PR smell and are blocked here on purpose."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()

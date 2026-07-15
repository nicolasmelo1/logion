#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Dependency-change gate.

Snapshots every ``[project].dependencies``,
``[project.optional-dependencies]``, and ``[dependency-groups]`` table
from the workspace ``pyproject.toml`` files into ``.deps.lock.json``.
Any change to the dependency set must be accompanied by a matching
update to that lock file (``make update-deps-lock``).

Reviewers treat a diff in ``.deps.lock.json`` as a permission gate
against supply-chain drift — adding a dep can't slip in alongside
unrelated changes.

Usage:
  python scripts/check_deps_lock.py             # verify (CI / hooks)
  python scripts/check_deps_lock.py --update    # rewrite the lock
"""

from __future__ import annotations

import json
import os
import sys
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCK_PATH = os.path.join(ROOT, ".deps.lock.json")

PYPROJECTS = [
    "pyproject.toml",
    "packages/agent-companion/pyproject.toml",
    "packages/bot/pyproject.toml",
    "packages/cli/pyproject.toml",
    "packages/client/pyproject.toml",
    "packages/indexer/pyproject.toml",
    "packages/landing/pyproject.toml",
    "packages/skillmap/pyproject.toml",
]


def _load(path: str) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def extract(rel: str) -> dict[str, object]:
    """Return the dependency-relevant slices of one pyproject.toml.

    The returned dict has stable, sorted contents so the lock diff is
    minimal and reviewable.
    """
    data = _load(os.path.join(ROOT, rel))
    project = data.get("project", {})
    out: dict[str, object] = {
        "dependencies": sorted(project.get("dependencies", []) or []),
        "optional-dependencies": {
            group: sorted(deps)
            for group, deps in sorted(
                (project.get("optional-dependencies") or {}).items()
            )
        },
        "dependency-groups": {
            group: sorted(deps)
            for group, deps in sorted(
                (data.get("dependency-groups") or {}).items()
            )
        },
    }
    return out


def compute() -> dict[str, dict[str, object]]:
    return {rel: extract(rel) for rel in sorted(PYPROJECTS)}


def load_lock() -> dict[str, dict[str, object]]:
    if not os.path.isfile(LOCK_PATH):
        print(
            f"check_deps_lock: {LOCK_PATH} not found. "
            f"Run `make update-deps-lock`.",
            file=sys.stderr,
        )
        sys.exit(2)
    with open(LOCK_PATH) as fh:
        return json.load(fh)


def write_lock(data: dict[str, dict[str, object]]) -> None:
    with open(LOCK_PATH, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main() -> None:
    if "--update" in sys.argv:
        write_lock(compute())
        print(f"check_deps_lock: rewrote {LOCK_PATH}")
        return

    current = compute()
    locked = load_lock()
    if current == locked:
        print("check_deps_lock: dependency set matches lock.")
        return

    print(
        "check_deps_lock: dependency set has changed but "
        ".deps.lock.json was not updated.\n"
        "Run `make update-deps-lock` and review the diff before "
        "committing. The lock file is a deliberate review gate; do "
        "not bypass it."
    )
    # Print a short summary so the failure is actionable.
    for rel in sorted(set(current) | set(locked)):
        if current.get(rel) != locked.get(rel):
            print(f"  changed: {rel}")
    sys.exit(1)


if __name__ == "__main__":
    main()

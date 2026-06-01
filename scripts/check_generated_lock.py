#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Lock file for upstream-generated artifacts.

Files listed in ``GENERATED_PATHS`` are produced by an upstream sync
workflow, not edited by hand. We track their SHA-256 in
``.generated-files.lock`` so any unintended edit shows up as a CI
failure with a clear "this is generated" message.

Usage:
  python scripts/check_generated_lock.py            # verify (CI / hooks)
  python scripts/check_generated_lock.py --update   # rewrite the lock
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCK_PATH = os.path.join(ROOT, ".generated-files.lock")

# Globs would be nice but the set is small and explicit is safer.
GENERATED_PATHS: list[str] = [
    "contracts/openapi/v1.json",
    "packages/client/src/logion/v1/_generated/__init__.py",
    "packages/client/src/logion/v1/_generated/operations.py",
    "packages/client/src/logion/v1/_types/generated/__init__.py",
    "packages/client/src/logion/v1/_types/generated/v1.py",
]


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute() -> dict[str, str]:
    out: dict[str, str] = {}
    missing: list[str] = []
    for rel in GENERATED_PATHS:
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            missing.append(rel)
            continue
        out[rel] = sha256_of(full)
    if missing:
        print(
            "check_generated_lock: expected files are missing:\n  "
            + "\n  ".join(missing),
            file=sys.stderr,
        )
        sys.exit(2)
    return out


def load_lock() -> dict[str, str]:
    if not os.path.isfile(LOCK_PATH):
        print(
            f"check_generated_lock: {LOCK_PATH} not found. "
            f"Run `make update-generated-lock` after a sync.",
            file=sys.stderr,
        )
        sys.exit(2)
    with open(LOCK_PATH) as fh:
        return json.load(fh)


def write_lock(data: dict[str, str]) -> None:
    with open(LOCK_PATH, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main() -> None:
    if "--update" in sys.argv:
        write_lock(compute())
        print(f"check_generated_lock: rewrote {LOCK_PATH}")
        return

    current = compute()
    locked = load_lock()
    mismatched = sorted(
        rel
        for rel in set(current) | set(locked)
        if current.get(rel) != locked.get(rel)
    )
    if not mismatched:
        print("check_generated_lock: all generated files match lock.")
        return

    print("check_generated_lock: generated files differ from lock:")
    for rel in mismatched:
        cur = current.get(rel, "<missing>")
        was = locked.get(rel, "<missing>")
        print(f"  {rel}\n    locked:  {was}\n    current: {cur}")
    print(
        "\nThese files are produced by the upstream sync workflow and "
        "should not be edited by hand. If this change came from a "
        "legitimate sync, run `make update-generated-lock` and commit "
        "the result alongside the file changes."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()

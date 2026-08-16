#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One-shot script: add SPDX-License-Identifier headers to .py files.

Run this once, then delete the script. The SPDX headers stay.

    uv run python scripts/_add_spdx.py

After running, verify with:

    grep -L "SPDX-License-Identifier" $(find packages -name '*.py')

The above should print nothing (i.e. every .py file has the header).
"""

from __future__ import annotations

import os

SPDX_LINE = "# SPDX-License-Identifier: MIT\n"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACKAGES_DIR = os.path.join(ROOT, "packages")


def add_spdx(filepath: str) -> bool:
    """Add an SPDX header when absent; return True when changed."""
    with open(filepath, encoding="utf-8") as fh:
        lines = fh.readlines()

    # Check if SPDX header already exists
    for line in lines[:5]:
        if "SPDX-License-Identifier" in line:
            return False

    # Find insertion point: after shebang if present, otherwise first line
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1

    lines.insert(insert_at, SPDX_LINE)

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    return True


def main() -> None:
    changed = 0
    total = 0

    for dirpath, _dirnames, filenames in os.walk(PACKAGES_DIR):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, fname)
            total += 1
            if add_spdx(filepath):
                relpath = os.path.relpath(filepath, ROOT)
                print(f"  Added SPDX header to {relpath}")
                changed += 1

    print(f"\nDone: {changed}/{total} files updated.")
    if changed:
        print(
            "Verify with: grep -L 'SPDX-License-Identifier' "
            "$(find packages -name '*.py')"
        )
    print("You can now delete this script: scripts/_add_spdx.py")


if __name__ == "__main__":
    main()

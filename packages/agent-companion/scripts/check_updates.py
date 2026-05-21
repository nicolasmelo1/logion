#!/usr/bin/env python3
"""Check for available updates to installed Logion capabilities.

This is a planned CLI surface — currently a placeholder that
validates the local install state and reports installed versions.

Usage: python scripts/check_updates.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

INSTALL_BASE = Path(
    os.environ.get("LOGION_HOME", str(Path.home() / ".logion"))
)
INSTALLED_DIR = INSTALL_BASE / "installed"


def main() -> int:
    if not INSTALLED_DIR.is_dir():
        print("No installed capabilities found.")
        print(f"Expected directory: {INSTALLED_DIR}")
        return 0

    capabilities = sorted(INSTALLED_DIR.iterdir())
    if not capabilities:
        print("No installed capabilities found.")
        return 0

    print(f"Installed capabilities ({len(capabilities)}):")
    for cap_dir in capabilities:
        manifest = cap_dir / "course" / "capabilities.yaml"
        if manifest.is_file():
            print(f"  {cap_dir.name} (has manifest)")
        else:
            print(f"  {cap_dir.name} (no manifest)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

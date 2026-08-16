#!/usr/bin/env python3
"""Create isolated repositories and local state for native feedback dogfood."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    fixture = workspace / "xpto"
    home = workspace / "home-xpto"
    logion_home = home / ".logion"
    evidence = workspace / "evidence"
    for directory in (
        fixture,
        home,
        logion_home,
        evidence,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    if not (fixture / ".git").is_dir():
        subprocess.run(
            [
                "git",
                "init",
                "--quiet",
                "--initial-branch=main",
                str(fixture),
            ],
            check=True,
        )
    (fixture / "buggy.py").write_text(
        "def divide(total, count):\n    return total / count\n",
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps({
            "fixture_root": str(fixture),
            "isolated_home": str(home),
            "logion_home": str(logion_home),
            "evidence_dir": str(evidence),
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create local state for an isolated pending-usage check."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    repository = workspace / "acme"
    home = workspace / "home-acme"
    logion_home = home / ".logion"
    evidence = workspace / "evidence"
    for directory in (repository, home, logion_home, evidence):
        directory.mkdir(parents=True, exist_ok=True)
    if not (repository / ".git").is_dir():
        import subprocess

        subprocess.run(
            [
                "git",
                "init",
                "--quiet",
                "--initial-branch=main",
                str(repository),
            ],
            check=True,
        )
    sys.stdout.write(
        json.dumps({
            "isolated_home": str(home),
            "logion_home": str(logion_home),
            "evidence_dir": str(evidence),
            "repository": str(repository),
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

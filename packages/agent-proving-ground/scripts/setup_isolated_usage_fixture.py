#!/usr/bin/env python3
"""Create local state for an isolated pending-usage check.

``LOGION_HOME`` comes from the runner, which allocates one per agent. Using
it here rather than minting a second home is what makes this phase a proof:
the state it finds empty is the state the harness environment points at.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    repository = workspace / "acme"
    if len(sys.argv) > 2 and sys.argv[2]:
        logion_home = Path(sys.argv[2]).resolve()
    else:
        logion_home = workspace / ".logion"
    evidence = workspace / "evidence"
    for directory in (repository, logion_home, evidence):
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
            "logion_home": str(logion_home),
            "evidence_dir": str(evidence),
            "repository": str(repository),
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

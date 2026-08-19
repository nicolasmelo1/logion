#!/usr/bin/env python3
"""Create the customer repository and local state for native feedback dogfood.

The customer repository is the agent's workspace itself, not a
subdirectory of it. A harness reads project-level hook configuration from
the directory its session is rooted in, which is the workspace; if the
repository were a child, the hook the integration installs would land in
a settings file the live harness never reads, and the only way to produce
an observation would be to replay a payload by hand.

``LOGION_HOME`` is supplied by the runner rather than minted here. The
harness environment carries the same value, so the hook subprocess and
the agent's own commands spool into one state directory.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    if len(sys.argv) > 2 and sys.argv[2]:
        logion_home = Path(sys.argv[2]).resolve()
    else:
        logion_home = workspace / ".logion"
    evidence = workspace / "evidence"
    for directory in (workspace, logion_home, evidence):
        directory.mkdir(parents=True, exist_ok=True)
    if not (workspace / ".git").is_dir():
        subprocess.run(
            [
                "git",
                "init",
                "--quiet",
                "--initial-branch=main",
                str(workspace),
            ],
            check=True,
        )
    (workspace / "buggy.py").write_text(
        "def divide(total, count):\n    return total / count\n",
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps({
            "fixture_root": str(workspace),
            "logion_home": str(logion_home),
            "evidence_dir": str(evidence),
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

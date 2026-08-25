#!/usr/bin/env python3
"""Create the publisher workspace and local state for instrument dogfood.

The publisher workspace is the agent's own workspace. It holds the
projections output directory, evidence, and the Logion home used by
the publisher's CLI session.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    if len(sys.argv) > 2 and sys.argv[2]:
        logion_home = Path(sys.argv[2]).resolve()
    else:
        logion_home = workspace / ".logion"
    evidence = workspace / "evidence"
    projections = workspace / "projections"
    for directory in (workspace, logion_home, evidence, projections):
        directory.mkdir(parents=True, exist_ok=True)
    # A simple target file the skill can review.
    (workspace / "buggy.py").write_text(
        "def divide(total, count):\n    return total / count\n",
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps({
            "fixture_root": str(workspace),
            "logion_home": str(logion_home),
            "evidence_dir": str(evidence),
            "projections_dir": str(projections),
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
#!/usr/bin/env python3
"""Create the consumer workspace with NO Logion CLI on PATH.

The consumer workspace is the agent's own workspace. It must not have
the Logion CLI available — the entire point of projections is that an
end user never needs it. The fixture creates a workspace, a Logion
home for spool state, an evidence directory, and a target file the
skill can review.
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
    plugins = workspace / ".logion" / "plugins"
    for directory in (workspace, logion_home, evidence, plugins):
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
            "plugins_dir": str(plugins),
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

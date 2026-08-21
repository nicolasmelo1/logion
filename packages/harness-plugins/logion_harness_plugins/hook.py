# SPDX-License-Identifier: MIT
"""Hook entry point for PostToolUse events.

The harness calls this with a JSON payload on stdin.  The hook pipes a
minimal subset to ``logion usage observe`` and exits 0 regardless of
outcome — a broken observation must never break the harness that called
it.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys


def main() -> int:
    """Read stdin, pipe to logion, exit 0 always."""
    try:
        raw = sys.stdin.buffer.read(1024 * 1024)
    except Exception:
        return 0
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    harness = payload.get("_logion_harness", "unknown")
    clean = {k: v for k, v in payload.items() if not k.startswith("_logion_")}
    with contextlib.suppress(
        FileNotFoundError, subprocess.TimeoutExpired, OSError
    ):
        subprocess.run(
            [
                "logion",
                "usage",
                "observe",
                "--harness",
                harness,
                "--stdin",
            ],
            input=json.dumps(clean).encode(),
            timeout=10,
            capture_output=True,
            check=False,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Record a successful workflow run into recall history.

Hooks or agents call this after a workflow succeeds.  It updates
``workflows.json`` (incrementing ``success_count`` and refreshing
``last_success_at``) and rebuilds ``recall.json`` so the new evidence
is searchable on next recall.

Usage:
    python scripts/record_workflow.py \\
        --id verify-agent-companion \\
        --title "Verify agent companion package" \\
        --command "make -C packages/agent-companion verify"

Repeat ``--command`` for multi-step workflows.  ``--target`` overrides
``LOGION_HOME`` for tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from logion_agent_companion.local_state import (
    ensure_layout,
    record_workflow_success,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record a successful workflow run.",
    )
    parser.add_argument(
        "--id",
        required=True,
        dest="workflow_id",
        help="Stable identifier for the workflow.",
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Human-readable workflow title.",
    )
    parser.add_argument(
        "--command",
        action="append",
        default=[],
        help="Command included in the workflow (repeatable).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="Initial confidence score (0.0-1.0).",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Override LOGION_HOME.",
    )
    args = parser.parse_args()

    home = args.target or ensure_layout()
    record = record_workflow_success(
        workflow_id=args.workflow_id,
        title=args.title,
        commands=args.command,
        home=home,
        confidence=args.confidence,
    )
    json.dump(record, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

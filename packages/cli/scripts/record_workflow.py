#!/usr/bin/env python3
"""Thin CLI wrapper hooks/agents call after a workflow succeeds.

Exists as a standalone script (rather than only as
``logion recall record``) so a Claude Code Stop hook, shell alias, or
external agent can append to recall without going through the full
Logion CLI parser.

Usage::

    python scripts/record_workflow.py \\
        --id verify-companion \\
        --title "Verify companion package" \\
        --command "make -C packages/agent-companion verify"

Reads ``LOGION_HOME`` from the environment; use ``--target`` to
override.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cli._local_state import ensure_layout, record_workflow_success


def _confidence(value: str) -> float:
    """argparse ``type=`` validator for ``--confidence`` in [0.0, 1.0]."""
    try:
        f = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--confidence must be a float, got {value!r}"
        ) from exc
    if not (0.0 <= f <= 1.0):
        raise argparse.ArgumentTypeError(
            f"--confidence must be in [0.0, 1.0], got {f}"
        )
    return f


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True, help="Stable workflow id")
    parser.add_argument("--title", required=True, help="Human-readable title")
    parser.add_argument(
        "--command",
        action="append",
        required=True,
        help="One command in the workflow; pass --command multiple times",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Override LOGION_HOME for testing",
    )
    parser.add_argument(
        "--confidence",
        type=_confidence,
        default=0.5,
        help=(
            "Initial confidence when creating a new workflow record "
            "(must be in [0.0, 1.0])"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.command:
        print("ERROR: at least one --command is required.", file=sys.stderr)
        return 2
    home = ensure_layout(args.target)
    record = record_workflow_success(
        workflow_id=args.id,
        title=args.title,
        commands=args.command,
        home=home,
        confidence=args.confidence,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

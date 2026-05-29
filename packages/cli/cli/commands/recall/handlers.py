"""Handlers for the ``recall`` command group.

Read-only fuzzy lookup over installed capabilities and prior successful
workflows.  Recall never executes commands or installs anything; the
output is meant to be inspected by an agent or user before any further
action.
"""

from __future__ import annotations

import argparse
import sys

from cli._local_state import (
    ensure_layout,
    record_workflow_success,
    search_recall,
)
from cli._output import emit_json


def handle_recall_search(args: argparse.Namespace) -> int:
    """Search the local recall index for *query*."""
    home = ensure_layout(getattr(args, "target", None))
    results = search_recall(args.query, home, limit=args.limit)
    if getattr(args, "json_output", False):
        emit_json("logion.recall.search", results)
        return 0
    if not results:
        print(f"No recall matches for {args.query!r}.")
        return 0
    print(f"Top {len(results)} recall matches:")
    for entry in results:
        line = (
            f"  [{entry['type']}] {entry.get('id', '?')} "
            f"(confidence={entry.get('confidence', 0.0):.2f})"
        )
        if entry.get("danger_flags"):
            line += f" flags={','.join(entry['danger_flags'])}"
        print(line)
        title = entry.get("title")
        if title:
            print(f"    {title}")
    return 0


def handle_recall_record(args: argparse.Namespace) -> int:
    """Record a successful workflow run into recall history."""
    home = ensure_layout(getattr(args, "target", None))
    if not args.command:
        print(
            "ERROR: at least one --command is required.",
            file=sys.stderr,
        )
        return 2
    record = record_workflow_success(
        workflow_id=args.id,
        title=args.title,
        commands=args.command,
        home=home,
        confidence=args.confidence,
    )
    emit_json("logion.recall.record", record)
    return 0

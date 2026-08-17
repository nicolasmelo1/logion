# SPDX-License-Identifier: MIT
"""Handlers for the ``recall`` command group.

Read-only fuzzy lookup over installed capabilities, prior successful
workflows, and (future) local references.  Output carries
``confidence`` (0..1), ``band`` (HIGH|MEDIUM|LOW|NONE), and
``query_similarity``.  Confidence is recomputed per query; the on-disk
index stores only the persisted prior.  Recall never executes anything;
``danger_flags`` are surfaced for the agent's confirmation gating.
"""

from __future__ import annotations

import argparse
import sys

from cli._json import strings
from cli._local_state import (
    ensure_layout,
    record_workflow_success,
    search_recall,
)
from cli._output import emit_json


def handle_recall_search(args: argparse.Namespace) -> int:
    """Search the local recall index for *query*."""
    home = ensure_layout(getattr(args, "target", None))
    query = args.query.strip()
    payload = {
        "query": args.query,
        "matches": [],
        "total": 0,
        "limit": args.limit,
    }
    if not query:
        if getattr(args, "json_output", False):
            emit_json("logion.recall.search", payload)
            return 0
        print("Please clarify the recall query before searching.")
        return 0
    results = search_recall(query, home, limit=args.limit)
    payload = {
        "query": args.query,
        "matches": results,
        "total": len(results),
        "limit": args.limit,
    }
    if getattr(args, "json_output", False):
        emit_json("logion.recall.search", payload)
        return 0
    if not results:
        print(f"No recall matches for {args.query!r}.")
        return 0
    print(f"Top {len(results)} recall matches:")
    for entry in results:
        line = (
            f"  [{entry['type']}] {entry.get('id', '?')} "
            f"(confidence={entry.get('confidence', 0.0):.2f}, "
            f"band={entry.get('band', 'NONE')})"
        )
        if entry.get("danger_flags"):
            line += f" flags={','.join(strings(entry, 'danger_flags'))}"
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

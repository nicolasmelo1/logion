"""Parser registration for recall commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli._options import COMMON_PARSER

from .handlers import handle_recall_record, handle_recall_search


def _confidence(value: str) -> float:
    """argparse ``type=`` validator: float in the closed interval [0, 1]."""
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


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``recall`` subcommand group."""
    parser = subparsers.add_parser(
        "recall",
        help="Read-only fuzzy lookup over local capabilities and workflows",
    )
    sub = parser.add_subparsers(
        dest="recall_command",
        required=True,
    )

    search = sub.add_parser(
        "search",
        help="Search local recall index",
        parents=[COMMON_PARSER],
    )
    search.add_argument("query", metavar="QUERY")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--target", type=Path, default=None)
    search.set_defaults(handler=handle_recall_search)

    record = sub.add_parser(
        "record",
        help="Record a successful workflow run",
        parents=[COMMON_PARSER],
    )
    record.add_argument("--id", required=True)
    record.add_argument("--title", required=True)
    record.add_argument(
        "--command",
        action="append",
        default=[],
        help="Command included in the workflow (repeatable)",
    )
    record.add_argument(
        "--confidence",
        type=_confidence,
        default=0.5,
        help="Initial confidence score in [0.0, 1.0]",
    )
    record.add_argument("--target", type=Path, default=None)
    record.set_defaults(handler=handle_recall_record)

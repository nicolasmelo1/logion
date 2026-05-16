"""Reports command — create content reports."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error, require_non_empty_id
from cli._options import COMMON_PARSER
from cli._output import emit

_TARGET_TYPES = ["agent", "bounty", "bounty_submission", "course", "user"]
_REPORT_REASONS = [
    "spam",
    "scam",
    "harassment",
    "hate",
    "illegal",
    "ip_violation",
    "malware",
    "other",
]


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``reports`` subcommand group."""
    parser = subparsers.add_parser(
        "reports",
        help="Create content reports",
    )
    sub = parser.add_subparsers(
        dest="reports_command",
        required=True,
    )

    # ── create ──────────────────────────────────────────────────
    create = sub.add_parser(
        "create",
        help="Create a new report",
        parents=[COMMON_PARSER],
    )
    create.add_argument(
        "--target-type",
        required=True,
        choices=_TARGET_TYPES,
    )
    create.add_argument("--target-id", required=True)
    create.add_argument(
        "--reason",
        required=True,
        choices=_REPORT_REASONS,
    )
    create.add_argument("--description")
    create.add_argument("--yes", action="store_true")
    create.set_defaults(handler=handle_create)


def handle_create(args: argparse.Namespace) -> int:
    """Execute the reports create command."""
    empty = require_non_empty_id(args.target_id, "--target-id")
    if empty is not None:
        return empty
    refusal = require_yes(args.yes, "create report")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.reports.create(
            target_type=args.target_type,
            target_id=args.target_id,
            reason=args.reason,
            description=args.description,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

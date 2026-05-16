"""Reports command — create content reports."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error, require_non_empty_id, validate_uuid_id
from cli._options import COMMON_PARSER
from cli._output import emit
from cli._utils import only_not_none

_TARGET_TYPES = ["agent", "bounty", "bounty_submission", "course", "user"]
_UUID_TARGET_TYPES = frozenset(_TARGET_TYPES)
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


def _validate_target_id(target_type: str, target_id: str) -> int | None:
    """Validate ``target_id`` for the selected report target type."""
    if target_type in _UUID_TARGET_TYPES:
        return validate_uuid_id(target_id, "--target-id")
    return require_non_empty_id(target_id, "--target-id")


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
    # All current target types use UUID identifiers. Keep the validation
    # keyed off ``target_type`` so future non-UUID targets can be added by
    # updating ``_UUID_TARGET_TYPES`` instead of rewriting the handler.
    bad_id = _validate_target_id(args.target_type, args.target_id)
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "create this report")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {
                "target_type": args.target_type,
                "target_id": args.target_id,
                "reason": args.reason,
            },
            description=args.description,
        )
        result = client.v1.reports.create(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

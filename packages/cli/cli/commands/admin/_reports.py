# SPDX-License-Identifier: MIT
"""Admin abuse-report triage: list, get, resolve, dismiss."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import client_for
from cli._errors import handle_error, validate_uuid_id
from cli._options import COMMON_PARSER
from cli._output import emit
from cli._utils import only_not_none


def register_reports(sub: argparse._SubParsersAction) -> None:
    """Register the ``admin reports`` sub-group."""
    reports = sub.add_parser(
        "reports",
        help="Administer reports",
    )
    reports_sub = reports.add_subparsers(
        dest="admin_reports_command",
        required=True,
    )

    # reports list
    rl = reports_sub.add_parser(
        "list",
        help="List reports (admin view)",
        parents=[COMMON_PARSER],
    )
    rl.add_argument("--status")
    rl.add_argument("--severity")
    rl.add_argument("--target-type")
    rl.add_argument("--limit", type=int)
    rl.add_argument("--cursor")
    rl.set_defaults(handler=handle_admin_reports_list)

    # reports get
    rg = reports_sub.add_parser(
        "get",
        help="Get report details",
        parents=[COMMON_PARSER],
    )
    rg.add_argument("report_id", metavar="REPORT_ID")
    rg.set_defaults(handler=handle_admin_reports_get)

    # reports resolve
    rr = reports_sub.add_parser(
        "resolve",
        help="Resolve a report",
        parents=[COMMON_PARSER],
    )
    rr.add_argument("report_id", metavar="REPORT_ID")
    rr.add_argument("--note")
    rr.add_argument("--yes", action="store_true")
    rr.set_defaults(handler=handle_admin_reports_resolve)

    # reports dismiss
    rd = reports_sub.add_parser(
        "dismiss",
        help="Dismiss a report",
        parents=[COMMON_PARSER],
    )
    rd.add_argument("report_id", metavar="REPORT_ID")
    rd.add_argument("--reason", required=True)
    rd.add_argument("--yes", action="store_true")
    rd.set_defaults(handler=handle_admin_reports_dismiss)


def handle_admin_reports_list(args: argparse.Namespace) -> int:
    """Execute the admin reports list command."""
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            kwargs = only_not_none(
                {},
                status=args.status,
                severity=args.severity,
                target_type=args.target_type,
                limit=args.limit,
                cursor=args.cursor,
            )
            result = client.v1.admin.list_reports(**kwargs)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_admin_reports_get(args: argparse.Namespace) -> int:
    """Execute the admin reports get command."""
    bad_id = validate_uuid_id(args.report_id, "REPORT_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.get_report(report_id=args.report_id)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_admin_reports_resolve(args: argparse.Namespace) -> int:
    """Execute the admin reports resolve command."""
    bad_id = validate_uuid_id(args.report_id, "REPORT_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "resolve this report")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            kwargs = only_not_none(
                {"report_id": args.report_id},
                note=args.note,
            )
            result = client.v1.admin.resolve_report(**kwargs)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_admin_reports_dismiss(args: argparse.Namespace) -> int:
    """Execute the admin reports dismiss command."""
    bad_id = validate_uuid_id(args.report_id, "REPORT_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "dismiss this report")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.dismiss_report(
                report_id=args.report_id,
                reason=args.reason,
            )
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0

"""Notifications commands — read notifications and unread count."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._options import COMMON_PARSER
from cli._output import emit


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``notifications`` subcommand group."""
    parser = subparsers.add_parser(
        "notifications",
        help="List notifications and check unread count",
    )
    sub = parser.add_subparsers(
        dest="notifications_command",
        required=True,
    )

    # unread-count
    uc = sub.add_parser(
        "unread-count",
        help="Get unread notification count",
        parents=[COMMON_PARSER],
    )
    uc.set_defaults(handler=handle_unread_count)

    # list
    ls = sub.add_parser(
        "list",
        help="List notifications",
        parents=[COMMON_PARSER],
    )
    ls.add_argument("--unread-only", action="store_true", default=None)
    ls.add_argument("--notification-type")
    ls.add_argument("--limit", type=int)
    ls.add_argument("--cursor")
    ls.set_defaults(handler=handle_list)


def handle_unread_count(args: argparse.Namespace) -> int:
    """Execute the unread-count command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.notifications.get_unread_count()
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_list(args: argparse.Namespace) -> int:
    """Execute the notifications list command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.notifications.list(
            unread_only=args.unread_only,
            notification_type=getattr(args, "notification_type", None),
            limit=args.limit,
            cursor=getattr(args, "cursor", None),
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

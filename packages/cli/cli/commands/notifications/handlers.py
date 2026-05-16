"""Handlers for notifications commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._output import emit


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

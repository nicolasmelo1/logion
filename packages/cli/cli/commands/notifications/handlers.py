# SPDX-License-Identifier: MIT
"""Handlers for notifications commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._json import opt_int, opt_str
from cli._output import emit, emit_json, to_data, to_items


def _extract_count(raw: object) -> int:
    """Extract an integer count from whatever the SDK returns."""

    def _coerce(value: object) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            return int(value)
        return 0

    if isinstance(raw, int):
        return raw
    if isinstance(raw, dict):
        return _coerce(raw.get("unread_count", opt_int(raw, "count", 0)))
    return _coerce(getattr(raw, "unread_count", getattr(raw, "count", 0)))


def handle_unread_count(args: argparse.Namespace) -> int:
    """Execute the unread-count command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.notifications.get_unread_count()
        if config.json_output:
            emit_json(
                "logion.notifications.unread-count",
                {"unread_count": _extract_count(result)},
            )
        else:
            emit(result, json_output=False)
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
        if config.json_output:
            emit_json("logion.notifications.list", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_peek(args: argparse.Namespace) -> int:
    """Quick check: show unread count, list recent if any."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        raw_count = client.v1.notifications.get_unread_count()
        unread_count = _extract_count(raw_count)
        if unread_count == 0:
            if config.json_output:
                emit_json(
                    "logion.notifications.peek",
                    {"unread_count": 0, "items": []},
                )
            else:
                print("No unread notifications.")
            return 0
        items_raw = client.v1.notifications.list(
            unread_only=True,
            limit=5,
        )
        items = to_items(items_raw)
        if config.json_output:
            emit_json(
                "logion.notifications.peek",
                {"unread_count": unread_count, "items": items},
            )
        else:
            print(f"You have {unread_count} unread notification(s):")
            for item in items:
                title = (
                    opt_str(item, "title", "")
                    if isinstance(item, dict)
                    else ""
                )
                nid = opt_str(item, "id", "") if isinstance(item, dict) else ""
                print(f"  {nid}: {title}")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

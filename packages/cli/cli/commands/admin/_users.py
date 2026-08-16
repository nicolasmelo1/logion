# SPDX-License-Identifier: MIT
"""Admin user administration: get, suspend, unsuspend."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import client_for
from cli._errors import handle_error, validate_uuid_id
from cli._options import COMMON_PARSER
from cli._output import emit


def register_users(sub: argparse._SubParsersAction) -> None:
    """Register the ``admin users`` sub-group."""
    users = sub.add_parser(
        "users",
        help="Administer users",
    )
    users_sub = users.add_subparsers(
        dest="admin_users_command",
        required=True,
    )

    # users get
    ug = users_sub.add_parser(
        "get",
        help="Get user details",
        parents=[COMMON_PARSER],
    )
    ug.add_argument("user_id", metavar="USER_ID")
    ug.set_defaults(handler=handle_admin_users_get)

    # users suspend
    us = users_sub.add_parser(
        "suspend",
        help="Suspend a user",
        parents=[COMMON_PARSER],
    )
    us.add_argument("user_id", metavar="USER_ID")
    us.add_argument("--yes", action="store_true")
    us.set_defaults(handler=handle_admin_users_suspend)

    # users unsuspend
    uus = users_sub.add_parser(
        "unsuspend",
        help="Unsuspend a user",
        parents=[COMMON_PARSER],
    )
    uus.add_argument("user_id", metavar="USER_ID")
    uus.add_argument("--yes", action="store_true")
    uus.set_defaults(handler=handle_admin_users_unsuspend)


def handle_admin_users_get(args: argparse.Namespace) -> int:
    """Execute the admin users get command."""
    bad_id = validate_uuid_id(args.user_id, "USER_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.get_user(user_id=args.user_id)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_admin_users_suspend(args: argparse.Namespace) -> int:
    """Execute the admin users suspend command."""
    bad_id = validate_uuid_id(args.user_id, "USER_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "suspend this user")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.suspend_user(user_id=args.user_id)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_admin_users_unsuspend(args: argparse.Namespace) -> int:
    """Execute the admin users unsuspend command."""
    bad_id = validate_uuid_id(args.user_id, "USER_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "unsuspend this user")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.unsuspend_user(user_id=args.user_id)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0

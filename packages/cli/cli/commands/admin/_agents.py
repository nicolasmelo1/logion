# SPDX-License-Identifier: MIT
"""Admin agent administration: get, suspend, unsuspend."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import client_for
from cli._errors import handle_error, validate_uuid_id
from cli._options import COMMON_PARSER
from cli._output import emit


def register_agents(sub: argparse._SubParsersAction) -> None:
    """Register the ``admin agents`` sub-group."""
    agents = sub.add_parser(
        "agents",
        help="Administer agents",
    )
    agents_sub = agents.add_subparsers(
        dest="admin_agents_command",
        required=True,
    )

    # agents get
    ag = agents_sub.add_parser(
        "get",
        help="Get agent details",
        parents=[COMMON_PARSER],
    )
    ag.add_argument("agent_id", metavar="AGENT_ID")
    ag.set_defaults(handler=handle_admin_agents_get)

    # agents suspend
    asp = agents_sub.add_parser(
        "suspend",
        help="Suspend an agent",
        parents=[COMMON_PARSER],
    )
    asp.add_argument("agent_id", metavar="AGENT_ID")
    asp.add_argument("--yes", action="store_true")
    asp.set_defaults(handler=handle_admin_agents_suspend)

    # agents unsuspend
    aus = agents_sub.add_parser(
        "unsuspend",
        help="Unsuspend an agent",
        parents=[COMMON_PARSER],
    )
    aus.add_argument("agent_id", metavar="AGENT_ID")
    aus.add_argument("--yes", action="store_true")
    aus.set_defaults(handler=handle_admin_agents_unsuspend)


def handle_admin_agents_get(args: argparse.Namespace) -> int:
    """Execute the admin agents get command."""
    bad_id = validate_uuid_id(args.agent_id, "AGENT_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.get_agent(agent_id=args.agent_id)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_admin_agents_suspend(args: argparse.Namespace) -> int:
    """Execute the admin agents suspend command."""
    bad_id = validate_uuid_id(args.agent_id, "AGENT_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "suspend this agent")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.suspend_agent(agent_id=args.agent_id)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_admin_agents_unsuspend(args: argparse.Namespace) -> int:
    """Execute the admin agents unsuspend command."""
    bad_id = validate_uuid_id(args.agent_id, "AGENT_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "unsuspend this agent")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.admin.unsuspend_agent(agent_id=args.agent_id)
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0

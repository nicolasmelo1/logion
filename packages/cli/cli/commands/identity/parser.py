# SPDX-License-Identifier: MIT
"""Parser registration for identity commands."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .github import register_github
from .handlers import (
    handle_agents_add,
    handle_agents_rotate_key,
    handle_users_create,
)
from .onboarding import register_onboarding

_USER_ID_HELP = (
    "User id (defaults to the one saved in ~/.logion/credentials.json "
    "by users-create)"
)

_CREDENTIAL_HELP = (
    "User credential (passing it on the CLI is unsafe — "
    "leaves shell history; omit to use a hidden interactive prompt)"
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``identity`` subcommand group."""
    parser = subparsers.add_parser(
        "identity",
        help="Manage users and agents",
    )
    sub = parser.add_subparsers(
        dest="identity_command",
        required=True,
    )

    register_onboarding(sub)
    register_github(sub)

    users_create = sub.add_parser(
        "users-create",
        help="Create a user with a first agent",
        parents=[COMMON_PARSER],
    )
    users_create.add_argument("--email", required=True)
    users_create.add_argument("--password", help=_CREDENTIAL_HELP)
    users_create.add_argument("--agent-name", required=True)
    users_create.add_argument("--user-name")
    users_create.add_argument("--agent-description")
    users_create.set_defaults(handler=handle_users_create)

    agents_add = sub.add_parser(
        "agents-add",
        help="Add an agent to an existing user",
        parents=[COMMON_PARSER],
    )
    agents_add.add_argument("--user-id", help=_USER_ID_HELP)
    agents_add.add_argument("--agent-name", required=True)
    agents_add.add_argument("--password", help=_CREDENTIAL_HELP)
    agents_add.add_argument("--agent-description")
    agents_add.set_defaults(handler=handle_agents_add)

    rotate_key = sub.add_parser(
        "agents-rotate-key",
        help="Rotate an agent API key",
        parents=[COMMON_PARSER],
    )
    rotate_key.add_argument("--user-id", help=_USER_ID_HELP)
    rotate_key.add_argument("--agent-id", required=True)
    rotate_key.add_argument("--password", help=_CREDENTIAL_HELP)
    rotate_key.set_defaults(handler=handle_agents_rotate_key)

# SPDX-License-Identifier: MIT
"""Argparse wiring for the ``admin`` command group.

Gated by ``LOGION_ENABLE_ADMIN``. If the env var is not truthy the
``admin`` subcommand is hidden: the parser prints *No such command* to
stderr and exits with code 2.
"""

from __future__ import annotations

import argparse

from cli._config import is_admin_enabled
from cli._errors import print_err

from ._agents import register_agents
from ._reports import register_reports
from ._users import register_users
from .handlers import register_courses


def _handle_disabled(args: argparse.Namespace) -> int:  # noqa: ARG001
    """Exit with code 2 — admin is not enabled."""
    print_err("No such command")
    return 2


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``admin`` subcommand group.

    If ``LOGION_ENABLE_ADMIN`` is not truthy, adds a stub parser that
    exits with code 2 and prints *No such command* to stderr.
    """
    if not is_admin_enabled():
        parser = subparsers.add_parser(
            "admin",
            help=argparse.SUPPRESS,
            add_help=False,
        )
        parser.set_defaults(handler=_handle_disabled)
        return

    parser = subparsers.add_parser("admin", help="Admin operations")
    sub = parser.add_subparsers(dest="admin_command", required=True)
    register_courses(sub)
    register_users(sub)
    register_agents(sub)
    register_reports(sub)

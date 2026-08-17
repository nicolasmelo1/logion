# SPDX-License-Identifier: MIT
"""Argparse wiring for the ``workspace`` command group."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER

from .handlers import (
    handle_checkout,
    handle_evidence,
    handle_init,
    handle_status,
    handle_switch,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``workspace`` subcommand group."""
    parser = subparsers.add_parser(
        "workspace",
        help="Local bounty workspace management",
    )
    sub = parser.add_subparsers(
        dest="workspace_command",
        required=True,
    )

    # ── init ────────────────────────────────────────────────────
    init = sub.add_parser(
        "init",
        help="Initialise a new bounty workspace",
        parents=[COMMON_PARSER],
    )
    init.add_argument(
        "--workspace",
        default=None,
        help=("Workspace root (default: .logion/bounty-workspace)"),
    )
    init.add_argument(
        "--path",
        default=None,
        help="Deprecated alias for --workspace",
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing state.json",
    )
    init.set_defaults(handler=handle_init)

    # ── status ─────────────────────────────────────────────────
    status = sub.add_parser(
        "status",
        help="Print current workspace state",
        parents=[COMMON_PARSER],
    )
    status.add_argument(
        "--workspace",
        default=None,
        help="Workspace root (default: .logion/bounty-workspace)",
    )
    status.set_defaults(handler=handle_status)

    # ── checkout ────────────────────────────────────────────────
    checkout = sub.add_parser(
        "checkout",
        help="Check out a bounty submission",
        parents=[COMMON_PARSER],
    )
    checkout.add_argument("bounty_id", help="Bounty UUID")
    checkout.add_argument("submission_id", help="Submission UUID")
    checkout.add_argument(
        "--workspace",
        default=None,
        help="Workspace root (default: .logion/bounty-workspace)",
    )
    checkout.add_argument(
        "--force",
        action="store_true",
        help="Overwrite dirty files in current/",
    )
    checkout.set_defaults(handler=handle_checkout)

    # ── switch ──────────────────────────────────────────────────
    switch = sub.add_parser(
        "switch",
        help="Archive current and check out another submission",
        parents=[COMMON_PARSER],
    )
    switch.add_argument("bounty_id", help="Bounty UUID")
    switch.add_argument("submission_id", help="Submission UUID")
    switch.add_argument(
        "--workspace",
        default=None,
        help="Workspace root (default: .logion/bounty-workspace)",
    )
    switch.add_argument(
        "--force",
        action="store_true",
        help="Discard dirty files in current/",
    )
    switch.set_defaults(handler=handle_switch)

    # ── evidence ────────────────────────────────────────────────
    evidence = sub.add_parser(
        "evidence",
        help="Build an evidence manifest from current/",
        parents=[COMMON_PARSER],
    )
    evidence.add_argument(
        "--workspace",
        default=None,
        help="Workspace root (default: .logion/bounty-workspace)",
    )
    evidence.add_argument(
        "--output",
        default=None,
        help=(
            "Output path for evidence JSON"
            " (default: <workspace>/evidence.json)"
        ),
    )
    evidence.set_defaults(handler=handle_evidence)

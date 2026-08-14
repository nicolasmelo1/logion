# SPDX-License-Identifier: MIT
"""Parser registration for resource reconciliation."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from cli._harness.scopes import ALIASES, VALID_SCOPES
from cli._options import COMMON_PARSER


def register_reconcile(
    sub: argparse._SubParsersAction,
    lazy_handler: Callable[[str], Callable[..., int]],
    harness_choices: Sequence[str],
) -> None:
    """Register the read-only native reconciliation command."""
    reconcile = sub.add_parser(
        "reconcile",
        help="Match local installations to catalog resources (read-only)",
        parents=[COMMON_PARSER],
    )
    reconcile.add_argument(
        "--from",
        dest="source",
        default="all",
        choices=["skills", "plugins", "hf", "logion", "all"],
    )
    reconcile.add_argument(
        "--harness", default="all", choices=["all", *harness_choices]
    )
    reconcile.add_argument(
        "--scope",
        default="all",
        choices=sorted({"all", *VALID_SCOPES, *ALIASES.keys()}),
    )
    reconcile.add_argument("--dry-run", action="store_true", default=False)
    reconcile.add_argument("--cwd", default=None)
    reconcile.set_defaults(handler=lazy_handler("handle_resources_reconcile"))

# SPDX-License-Identifier: MIT
"""Parser registration for the ``logion instrument`` command.

Usage::

    logion instrument RESOURCE_VERSION \\
        --targets agent-plugin,static-skill \\
        --events activated,completed,failed \\
        --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cli._options import COMMON_PARSER

from ._constants import (
    DELIVERY_MODE_CHOICES,
    EVENT_CHOICES,
    TARGET_CHOICES,
)
from .handlers import handle_instrument


def _comma_list(value: str) -> list[str]:
    """Split a comma-separated string into a stripped, non-empty list."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _targets_type(value: str) -> list[str]:
    """Argparse type callback for ``--targets``."""
    items = _comma_list(value)
    invalid = [item for item in items if item not in TARGET_CHOICES]
    if invalid:
        raise argparse.ArgumentTypeError(
            f"unknown target(s): {', '.join(invalid)}; "
            f"choose from {', '.join(TARGET_CHOICES)}"
        )
    return items


def _events_type(value: str) -> list[str]:
    """Argparse type callback for ``--events``."""
    items = _comma_list(value)
    invalid = [item for item in items if item not in EVENT_CHOICES]
    if invalid:
        raise argparse.ArgumentTypeError(
            f"unknown event(s): {', '.join(invalid)}; "
            f"choose from {', '.join(EVENT_CHOICES)}"
        )
    return items


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``instrument`` subcommand."""
    parser = subparsers.add_parser(
        "instrument",
        help=(
            "Generate a projection tree from a canonical ResourceVersion "
            "(publisher-side authoring command)"
        ),
        parents=[COMMON_PARSER],
    )
    parser.add_argument(
        "resource_version",
        metavar="RESOURCE_VERSION",
        help=(
            "Canonical resource version identifier (e.g. "
            "urn:air:example.com:skill:review-helper@1.4.2)"
        ),
    )
    parser.add_argument(
        "--targets",
        type=_targets_type,
        required=True,
        help=(
            "Comma-separated projection targets: " + ", ".join(TARGET_CHOICES)
        ),
    )
    parser.add_argument(
        "--events",
        type=_events_type,
        default=None,
        help=(
            "Comma-separated events to instrument "
            "(default: all supported events)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Directory to write the projection tree into "
            "(default: ./<resource-slug>)"
        ),
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=None,
        help=(
            "Path to a pre-validated instrumentation profile JSON. "
            "If omitted, a default profile is generated from the "
            "ResourceVersion."
        ),
    )
    parser.add_argument(
        "--delivery-endpoint",
        default=None,
        help=(
            "Concrete HTTPS endpoint for publisher receipts. "
            "Required when generating a profile (not when --profile "
            "is supplied)."
        ),
    )
    parser.add_argument(
        "--delivery-mode",
        choices=DELIVERY_MODE_CHOICES,
        default="asynchronous-batch",
    )
    parser.add_argument(
        "--max-batch",
        type=int,
        default=20,
        help="Maximum batch size for asynchronous delivery (default: 20)",
    )
    parser.add_argument(
        "--max-spool-bytes",
        type=int,
        default=262144,
        help="Maximum local spool size in bytes (default: 262144)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help=("Print the plan and diff without writing any files (default)"),
    )
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help=(
            "Execute the write after approval. Requires explicit "
            "confirmation unless --yes is also passed."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Approve the plan without interactive confirmation.",
    )
    parser.add_argument(
        "--client",
        default=None,
        help=(
            "Override the client name for capability.json tier "
            "resolution (e.g. claude-code, codex, hermes)."
        ),
    )
    parser.set_defaults(handler=handle_instrument)

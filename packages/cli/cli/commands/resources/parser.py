# SPDX-License-Identifier: MIT
"""Parser registration for resources commands."""

from __future__ import annotations

import argparse

from cli._harness import adapter_names
from cli._harness.scopes import VALID_SCOPES
from cli._options import COMMON_PARSER

from .handlers import (
    handle_resources_acquire,
    handle_resources_get,
    handle_resources_inventory,
    handle_resources_search,
    handle_resources_versions,
)

_HARNESS_CHOICES = sorted(adapter_names())


def register(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register the ``resources`` subcommand group."""
    parser = subparsers.add_parser(
        "resources",
        help="Search and browse generic indexed resources",
    )
    sub = parser.add_subparsers(
        dest="resources_command",
        required=True,
    )

    search = sub.add_parser(
        "search",
        help="Search indexed resources",
        parents=[COMMON_PARSER],
    )
    search.add_argument("query", metavar="QUERY")
    search.add_argument(
        "--resource-type",
        default=None,
        help=(
            "Filter by resource type "
            "(skill, plugin, mcp_server, model, course)"
        ),
    )
    search.add_argument(
        "--tags", default=None, help="Comma-separated tag filter"
    )
    search.add_argument("--limit", type=int, default=5)
    search.add_argument(
        "--verbose",
        action="store_true",
        default=False,
    )
    search.set_defaults(handler=handle_resources_search)

    get = sub.add_parser(
        "get",
        help="Get detail for a single indexed resource",
        parents=[COMMON_PARSER],
    )
    get.add_argument("resource_id", metavar="RESOURCE_ID")
    get.set_defaults(handler=handle_resources_get)

    versions = sub.add_parser(
        "versions",
        help="List available versions of a resource",
        parents=[COMMON_PARSER],
    )
    versions.add_argument("resource_id", metavar="RESOURCE_ID")
    versions.add_argument("--limit", type=int, default=None)
    versions.set_defaults(handler=handle_resources_versions)

    acquire = sub.add_parser(
        "acquire",
        help="Plan acquiring a resource into a harness scope (dry-run)",
        parents=[COMMON_PARSER],
    )
    acquire.add_argument("resource_id", metavar="RESOURCE_ID")
    acquire.add_argument(
        "--scope",
        default="repo-root",
        choices=sorted(VALID_SCOPES),
        help="Target scope (default: repo-root)",
    )
    acquire.add_argument(
        "--harness",
        choices=_HARNESS_CHOICES,
        required=True,
        help="Target harness adapter",
    )
    acquire.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Zero-write plan only (the default in 15.9.1)",
    )
    acquire.add_argument(
        "--cwd",
        default=None,
        help="Override the working directory for scope resolution",
    )
    acquire.add_argument(
        "--repo-root",
        default=None,
        help="Override the detected repository root",
    )
    acquire.set_defaults(handler=handle_resources_acquire)

    inventory = sub.add_parser(
        "inventory",
        help="Scan a harness's native locations and list found resources",
        parents=[COMMON_PARSER],
    )
    inventory.add_argument(
        "--harness",
        choices=_HARNESS_CHOICES,
        required=True,
        help="Harness adapter to scan",
    )
    inventory.add_argument(
        "--cwd",
        default=None,
        help="Override the working directory for scope resolution",
    )
    inventory.add_argument(
        "--repo-root",
        default=None,
        help="Override the detected repository root",
    )
    inventory.set_defaults(handler=handle_resources_inventory)

    return parser

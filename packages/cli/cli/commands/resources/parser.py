# SPDX-License-Identifier: MIT
"""Parser registration for resources commands."""

from __future__ import annotations

import argparse

from cli._harness import adapter_names
from cli._harness.scopes import ALIASES, VALID_SCOPES
from cli._options import COMMON_PARSER

from .parser_reconcile import register_reconcile

_HARNESS_CHOICES = sorted([*adapter_names(), "custom"])


def _resource_limit(value: str) -> int:
    """Parse an OpenAPI-constrained resource list limit."""
    limit = int(value)
    if not 1 <= limit <= 100:
        raise argparse.ArgumentTypeError("limit must be between 1 and 100")
    return limit


def _lazy_handler(name: str):
    def dispatch(args):
        from importlib import import_module

        return getattr(import_module(".handlers", __package__), name)(args)

    return dispatch


def register(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register the ``resources`` subcommand group."""
    parser = subparsers.add_parser(
        "resources",
        help="List and browse generic resources",
    )
    sub = parser.add_subparsers(
        dest="resources_command",
        required=True,
    )

    list_parser = sub.add_parser(
        "list",
        help="List generic resources",
        parents=[COMMON_PARSER],
    )
    list_parser.set_defaults(query=None, tags=None)
    list_parser.add_argument(
        "--resource-type",
        default=None,
        help=(
            "Filter by resource type "
            "(agent_skill, agent_plugin, mcp_server, model)"
        ),
    )
    list_parser.add_argument(
        "--lifecycle-status", default=None, help="Filter by lifecycle status"
    )
    list_parser.add_argument("--cursor", default=None)
    list_parser.add_argument("--limit", type=_resource_limit, default=50)
    list_parser.add_argument("--verbose", action="store_true", default=False)
    list_parser.set_defaults(handler=_lazy_handler("handle_resources_search"))

    search = sub.add_parser(
        "search",
        help="Compatibility alias for resources list (query/tags unsupported)",
        parents=[COMMON_PARSER],
    )
    search.add_argument("query", metavar="QUERY", nargs="?", default=None)
    search.add_argument("--tags", default=None)
    search.add_argument("--resource-type", default=None)
    search.add_argument("--lifecycle-status", default=None)
    search.add_argument("--cursor", default=None)
    search.add_argument("--limit", type=_resource_limit, default=50)
    search.add_argument("--verbose", action="store_true", default=False)
    search.set_defaults(handler=_lazy_handler("handle_resources_search"))

    get = sub.add_parser(
        "get",
        help="Get detail for a generic resource UUID",
        parents=[COMMON_PARSER],
    )
    get.add_argument("resource_id", metavar="RESOURCE_ID")
    get.set_defaults(handler=_lazy_handler("handle_resources_get"))

    versions = sub.add_parser(
        "versions",
        help="List available versions of a resource UUID",
        parents=[COMMON_PARSER],
    )
    versions.add_argument("resource_id", metavar="RESOURCE_ID")
    versions.add_argument("--limit", type=_resource_limit, default=None)
    versions.set_defaults(handler=_lazy_handler("handle_resources_versions"))

    acquire = sub.add_parser(
        "acquire",
        help="Plan acquiring a resource into a harness scope (dry-run)",
        parents=[COMMON_PARSER],
    )
    acquire.add_argument("resource_id", metavar="RESOURCE_ID")
    acquire.add_argument(
        "--version",
        dest="version",
        default=None,
        help="Specific resource version UUID (default: latest)",
    )
    acquire.add_argument(
        "--channel",
        dest="channel",
        default="auto",
        choices=[
            "auto",
            "logion_bundle",
            "npx_skills",
            "npx_plugins",
            "hf",
            "git",
            "manual",
        ],
        help="Preferred acquisition channel (default: auto)",
    )
    acquire.add_argument(
        "--scope",
        default=None,
        choices=sorted(VALID_SCOPES | ALIASES.keys()),
        help=(
            "Target scope (default: repo-root inside Git; "
            "user with confirmation outside Git)"
        ),
    )
    acquire.add_argument(
        "--harness",
        choices=_HARNESS_CHOICES,
        required=True,
        help="Target harness adapter",
    )
    acquire.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Produce a zero-write acquisition plan (default)",
    )
    acquire.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Execute acquisition after confirmation",
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
    acquire.add_argument(
        "--repo-parent",
        default=None,
        help="Explicit parent directory for repo-parent scope",
    )
    acquire.add_argument(
        "--target-path",
        default=None,
        help="Explicit skills directory for the custom harness",
    )
    acquire.set_defaults(handler=_lazy_handler("handle_resources_acquire"))

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
    inventory.add_argument(
        "--target-path",
        default=None,
        help="Explicit skills directory for the custom harness",
    )
    inventory.add_argument(
        "--scope",
        default="all",
        choices=sorted({"all", *VALID_SCOPES, *ALIASES.keys()}),
        help="Limit inventory to one scope (default: all)",
    )
    inventory.set_defaults(handler=_lazy_handler("handle_resources_inventory"))

    acquire.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Approve the displayed acquisition plan without prompting",
    )

    distributions = sub.add_parser(
        "distributions",
        help="List acquisition channels for a resource version",
        parents=[COMMON_PARSER],
    )
    distributions.add_argument("resource_id", metavar="RESOURCE_ID")
    distributions.add_argument(
        "--version",
        dest="version",
        default=None,
        help="Specific version UUID (default: latest)",
    )
    distributions.set_defaults(
        handler=_lazy_handler("handle_resources_distributions")
    )

    register_reconcile(sub, _lazy_handler, _HARNESS_CHOICES)

    return parser

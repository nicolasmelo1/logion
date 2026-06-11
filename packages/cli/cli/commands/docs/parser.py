# SPDX-License-Identifier: MIT
"""Parser registration for the ``docs`` command."""

from __future__ import annotations

import argparse

from .handlers import handle_docs


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register offline documentation commands."""
    parser = subparsers.add_parser(
        "docs",
        help="Read version-matched Logion documentation offline",
        description=(
            "Read the documentation bundled with this CLI version. "
            "Run without an article to list available documentation."
        ),
    )
    parser.add_argument("article", nargs="?", metavar="ARTICLE")
    parser.add_argument("query", nargs="*", metavar="QUERY")
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum search results"
    )
    parser.add_argument("--json", dest="json_output", action="store_true")
    parser.set_defaults(handler=handle_docs)

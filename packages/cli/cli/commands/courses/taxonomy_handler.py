# SPDX-License-Identifier: MIT
"""Handler and parser registration for ``courses taxonomy`` commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli._config import resolve_config_from_args
from cli._json import strings
from cli._options import COMMON_PARSER
from cli._output import emit_json

from .taxonomy_suggest import suggest_taxonomy


def handle_taxonomy_suggest(args: argparse.Namespace) -> int:
    """Produce deterministic category/tag suggestions for a local bundle."""
    config = resolve_config_from_args(args)
    bundle_dir: Path = args.bundle_dir
    result = suggest_taxonomy(bundle_dir)
    if config.json_output:
        emit_json("logion.courses.taxonomy.suggest", result)
    else:
        lines: list[str] = []
        cats = strings(result, "category_suggestions")
        lines.append(f"category_suggestions: {', '.join(cats)}")
        tags = strings(result, "tag_suggestions")
        lines.append(f"tag_suggestions: {', '.join(tags)}")
        rejected = strings(result, "rejected_reserved")
        if rejected:
            lines.append(f"rejected_reserved: {', '.join(rejected)}")
        lines.append(f"source: {', '.join(strings(result, 'source'))}")
        print("\n".join(lines))
    return 0


def register_taxonomy(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Register the ``courses taxonomy`` subcommand group."""
    taxonomy = subparsers.add_parser(
        "taxonomy",
        help="Suggest category and tags from local course bundle text",
    )
    taxonomy_sub = taxonomy.add_subparsers(
        dest="courses_taxonomy_command",
        required=True,
    )

    suggest = taxonomy_sub.add_parser(
        "suggest",
        help="Suggest category and tags from SKILL.md and capabilities.yaml",
        parents=[COMMON_PARSER],
    )
    suggest.add_argument(
        "--bundle-dir",
        type=Path,
        required=True,
        help="Path to the course bundle directory",
    )
    suggest.set_defaults(handler=handle_taxonomy_suggest)

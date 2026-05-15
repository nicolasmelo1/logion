"""Shared CLI option definitions."""

from __future__ import annotations

import argparse


def add_common_options(
    parser: argparse.ArgumentParser,
) -> None:
    """Add shared CLI options (--api-key, --base-url, etc.)."""
    parser.add_argument("--api-key")
    parser.add_argument("--base-url")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
    )
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--max-retries", type=int)

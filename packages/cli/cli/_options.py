# SPDX-License-Identifier: MIT
"""Shared CLI option definitions."""

from __future__ import annotations

import argparse


def build_common_parser() -> argparse.ArgumentParser:
    """Build a parent parser with shared CLI options.

    Use this via ``parents=[build_common_parser()]`` on leaf subcommands
    so that argparse merges common options correctly without overwriting
    user-supplied values.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--api-key")
    parent.add_argument("--base-url")
    parent.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
    )
    parent.add_argument("--timeout", type=float)
    parent.add_argument("--max-retries", type=int)
    parent.add_argument(
        "--no-onboarding",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Never run first-run onboarding for this invocation.",
    )
    return parent


# Module-level singleton so the parent parser is built once.
COMMON_PARSER = build_common_parser()

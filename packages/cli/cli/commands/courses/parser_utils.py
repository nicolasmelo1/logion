# SPDX-License-Identifier: MIT
"""Shared parser helpers for courses commands."""

from __future__ import annotations

import argparse


def add_tag_arguments(
    parser: argparse.ArgumentParser,
    *,
    default: list[str] | None,
) -> None:
    """Add ``--tag`` and ``--clear-tags`` arguments."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=default,
        help="Tag to add (can be specified multiple times)",
    )
    if default is None:
        group.add_argument(
            "--clear-tags",
            action="store_true",
            help="Remove all tags from the course",
        )


def add_category_argument(
    parser: argparse.ArgumentParser,
) -> None:
    """Add ``--category`` argument to a create or update parser."""
    parser.add_argument(
        "--category",
        default=None,
        help=(
            "Course category slug (e.g. devops, security, writing). "
            "Unknown slugs are rejected by the API."
        ),
    )


def add_tristate_flag(
    parser: argparse.ArgumentParser,
    flag: str,
    *,
    dest: str,
) -> None:
    """Add a three-state boolean flag."""
    base = flag.removeprefix("--")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        flag,
        dest=dest,
        action="store_true",
        default=None,
    )
    group.add_argument(
        f"--no-{base}",
        dest=dest,
        action="store_false",
        default=None,
    )

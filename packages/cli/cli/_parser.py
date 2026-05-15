"""Argparse parser factory for the Logion CLI."""

from __future__ import annotations

import argparse

from cli._version import get_cli_version
from cli.commands import (
    course_reviews,
    courses,
    health,
    identity,
    listings,
    notifications,
    payments,
    reports,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="logion",
        description="Logion CLI for AI agents and marketplace operators.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_cli_version()}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    health.register(subparsers)
    identity.register(subparsers)
    listings.register(subparsers)
    notifications.register(subparsers)
    courses.register(subparsers)
    payments.register(subparsers)
    reports.register(subparsers)
    course_reviews.register(subparsers)

    return parser

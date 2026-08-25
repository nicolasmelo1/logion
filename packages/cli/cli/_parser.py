# SPDX-License-Identifier: MIT
"""Argparse parser factory for the Logion CLI."""

from __future__ import annotations

import argparse

from cli._version import __version__
from cli.commands import (
    admin,
    bounties,
    completion,
    course_reviews,
    courses,
    docs,
    doctor,
    feedback,
    health,
    identity,
    indexed,
    instrument,
    integrations,
    listings,
    notifications,
    payments,
    recall,
    reports,
    resources,
    skills,
    update,
    usage,
)
from cli.commands import (
    credits as credits_mod,
)
from cli.commands import (
    referrals as referrals_mod,
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
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--no-onboarding",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Never run first-run onboarding for this invocation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    health.register(subparsers)
    doctor.register(subparsers)
    identity.register(subparsers)
    indexed.register(subparsers)
    listings.register(subparsers)
    notifications.register(subparsers)
    courses.register(subparsers)
    docs.register(subparsers)
    payments.register(subparsers)
    credits_mod.register(subparsers)
    referrals_mod.register(subparsers)
    reports.register(subparsers)
    course_reviews.register(subparsers)
    admin.register(subparsers)
    bounties.register(subparsers)
    skills.register(subparsers)
    resources.register(subparsers)
    recall.register(subparsers)
    update.register(subparsers)
    completion.register(subparsers)
    feedback.register(subparsers)
    usage.register(subparsers)
    integrations.register(subparsers)
    instrument.register(subparsers)

    # Top-level `logion onboarding` alias — same handler as
    # `logion identity onboarding`.
    from cli.commands.identity.onboarding import register_onboarding

    register_onboarding(subparsers)

    return parser

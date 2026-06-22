# SPDX-License-Identifier: MIT
"""First-run onboarding trigger.

Decides whether to run onboarding before dispatching a command. The
matrix is deliberately conservative: never hijack help/version/docs,
never prompt in CI/non-interactive shells, always respect --no-onboarding.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from cli._credentials import is_onboarded

# Commands that must never trigger onboarding (read-only / informational).
SKIP_COMMANDS: frozenset[str] = frozenset({"docs", "onboarding"})

# Commands that need identity/companion/local-state to be useful.
NEEDS_SETUP_COMMANDS: frozenset[str] = frozenset({
    "courses",
    "credits",
    "payments",
    "referrals",
    "reports",
    "course-reviews",
    "bounties",
    "listings",
    "skills",
    "recall",
})


@dataclass(frozen=True)
class TriggerDecision:
    should_run: bool
    reason: str  # "already-onboarded" | "no-tty" | "noninteractive-env" |
    # "no-onboarding-flag" | "skip-command" | "help-version" |
    # "command-needs-setup" | "unknown-command"


def is_noninteractive() -> bool:
    """True in CI / piped / explicitly-flagged non-interactive shells."""
    if os.getenv("LOGION_NONINTERACTIVE"):
        return True
    return not sys.stdin.isatty() or not sys.stdout.isatty()


def decide(argv: list[str], args: argparse.Namespace) -> TriggerDecision:
    """Pure decision: given parsed args + raw argv, run onboarding?"""
    if "--help" in argv or "-h" in argv or "--version" in argv:
        return TriggerDecision(should_run=False, reason="help-version")
    # ``--no-onboarding`` may appear before or after the subcommand;
    # argparse only populates ``args.no_onboarding`` when it precedes
    # the subcommand, so check the raw argv too.
    if "--no-onboarding" in argv or getattr(args, "no_onboarding", False):
        return TriggerDecision(should_run=False, reason="no-onboarding-flag")
    if os.getenv("LOGION_NO_ONBOARDING"):
        return TriggerDecision(should_run=False, reason="no-onboarding-flag")
    command = getattr(args, "command", None)
    if not isinstance(command, str):
        return TriggerDecision(should_run=False, reason="unknown-command")
    if command in SKIP_COMMANDS:
        return TriggerDecision(should_run=False, reason="skip-command")
    if command not in NEEDS_SETUP_COMMANDS:
        return TriggerDecision(should_run=False, reason="unknown-command")
    if is_onboarded():
        return TriggerDecision(should_run=False, reason="already-onboarded")
    if is_noninteractive():
        return TriggerDecision(should_run=False, reason="noninteractive-env")
    # ``--json`` means a machine consumer is piping stdout; never
    # hijack it with onboarding prompts or JSON of our own.
    if getattr(args, "json_output", False):
        return TriggerDecision(should_run=False, reason="json-output")
    return TriggerDecision(should_run=True, reason="command-needs-setup")

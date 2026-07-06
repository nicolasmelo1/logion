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
# ``listings`` is excluded because search/browse is public and read-only —
# forcing onboarding before a prospective user can explore the marketplace
# adds friction without value.
NEEDS_SETUP_COMMANDS: frozenset[str] = frozenset({
    "courses",
    "credits",
    "payments",
    "referrals",
    "reports",
    "course-reviews",
    "bounties",
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


def _is_help_or_version(argv: list[str]) -> bool:
    """True if argv contains a flag-level ``--help``/``-h``/``--version``.

    Only tokens that start with ``-`` are considered, so a positional
    value (e.g. a search query literally equal to ``--help``) does not
    trigger a false positive.
    """
    help_flags = {"--help", "-h", "--version"}
    return any(tok in help_flags for tok in argv if tok.startswith("-"))


def decide(argv: list[str], args: argparse.Namespace) -> TriggerDecision:
    """Pure decision: given parsed args + raw argv, run onboarding?"""
    if _is_help_or_version(argv):
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
    # LOGION_SETUP_TOKEN env var bypasses the non-interactive guard because
    # the token flow needs no prompts.  (The --setup-token CLI flag cannot
    # reach decide() from top-level commands because it is only defined on
    # the onboarding subparser, so argparse rejects it before this point.)
    if os.getenv("LOGION_SETUP_TOKEN"):
        return TriggerDecision(should_run=True, reason="setup-token")
    if is_noninteractive():
        return TriggerDecision(should_run=False, reason="noninteractive-env")
    # ``--json`` means a machine consumer is piping stdout; never
    # hijack it with onboarding prompts or JSON of our own.
    if getattr(args, "json_output", False):
        return TriggerDecision(should_run=False, reason="json-output")
    return TriggerDecision(should_run=True, reason="command-needs-setup")

# SPDX-License-Identifier: MIT
"""Auto-review opt-in for ``identity onboarding``.

Decides whether the user wants agents to post usage reviews
automatically, then applies that grant across the resolved harnesses via
their adapters.  Kept separate from the onboarding handler so the
identity-provisioning flow and the harness-permission flow stay small
and independently testable.
"""

from __future__ import annotations

import argparse
import sys

from cli._errors import print_err
from cli._harness.base import GrantResult, HarnessAdapter, HarnessConfigError


def _prompt_yes_no(question: str, *, default: bool = False) -> bool:
    """Prompt for y/n; *default* is used on empty input."""
    hint = "y/N" if not default else "Y/n"
    try:
        answer = input(f"{question} [{hint}]: ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer in {"y", "yes"}


def resolve_optin(args: argparse.Namespace) -> bool:
    """Decide whether to enable autopost: flag, prompt, or safe default."""
    from cli._credentials import save_autoreview_consent

    if args.enable_autopost is not None:
        decision = bool(args.enable_autopost)
    elif sys.stdin.isatty():
        print_err(
            "\nAuto-review lets agents post a usage review (rating 1-5, "
            "editable and removable, under your agent's identity, only "
            "for courses you have used) to the marketplace without "
            "prompting each time. Undo any time with "
            "`logion identity onboarding --no-enable-autopost`."
        )
        decision = _prompt_yes_no(
            "Enable automatic usage reviews?", default=False
        )
    else:
        decision = False
    # Persist consent best-effort: a write failure (read-only home,
    # permissions) must not abort onboarding.  Identity saving follows
    # the same warn-and-continue pattern.
    try:
        save_autoreview_consent(decision)
    except OSError as exc:
        print_err(f"Warning: could not save consent: {exc}")
    return decision


def apply(
    args: argparse.Namespace,
    adapters: list[HarnessAdapter],
) -> dict[str, object] | None:
    """Grant the autopost permission across the resolved harnesses.

    *adapters* is the harness selection resolved once by
    ``select_harnesses`` and shared with the companion step. Returns a
    JSON-safe summary, or ``None`` on an unparseable harness config.
    """
    if not adapters:
        # No harness selected/detected — nothing to grant.
        print_err(
            "Auto-review consent saved, but no harness was selected, so "
            "no permission rule was written."
        )
        return {"enabled": True, "scope": args.autopost_scope, "harnesses": []}

    grants: list[GrantResult] = []
    try:
        for adapter in adapters:
            grants.append(adapter.grant(args.autopost_scope))
    except HarnessConfigError as exc:
        print_err(f"Error: {exc}")
        return None

    for g in grants:
        verb = "already enabled" if g.already else "enabled"
        print_err(
            f"Auto-review {verb} for {g.harness} "
            f"({args.autopost_scope}: {g.path})."
        )
    return {
        "enabled": True,
        "scope": args.autopost_scope,
        "harnesses": [g.to_dict() for g in grants],
    }

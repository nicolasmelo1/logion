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
from cli._harness import adapter_names, detect_present, get_adapter
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


def _target_adapters(args: argparse.Namespace) -> list[HarnessAdapter] | None:
    """Resolve which harnesses to grant: ``--harness`` or auto-detected.

    Returns ``None`` only when an explicit ``--harness`` is unknown —
    the error message is printed by ``validate_explicit_harness``
    before this function is reached, so we return ``None`` silently
    to signal the hard error without duplicating the message.
    """
    if args.harness:
        adapter = get_adapter(args.harness)
        if adapter is None:
            return None
        return [adapter]
    present = detect_present()
    if not present:
        print_err(
            "No supported agent harness detected, so autopost was not "
            f"configured. Supported: {', '.join(adapter_names())}. "
            "Re-run with --harness <name> to force."
        )
    return present


def apply(args: argparse.Namespace) -> dict[str, object] | None:
    """Grant the autopost permission across the resolved harnesses.

    Returns a JSON-safe summary, or ``None`` on a hard error (unknown
    harness or an unparseable harness config).
    """
    adapters = _target_adapters(args)
    if adapters is None:
        # Unknown harness explicitly requested — a hard error.
        return None
    if not adapters:
        # No supported harness detected; already noted to the user.
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

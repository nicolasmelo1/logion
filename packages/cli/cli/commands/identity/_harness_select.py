# SPDX-License-Identifier: MIT
"""Harness selection for ``identity onboarding``.

Resolves which harness adapters the onboarding flow should configure
(auto-review grant + companion install). The same selection drives both
steps so the two never diverge.

Resolution order:
- explicit ``--harness`` (repeatable) → exactly those adapters, no prompt;
- a TTY with at least one detected harness → an interactive multi-select
  (nothing pre-selected — the user picks);
- otherwise (non-interactive, or no harness detected) → every detected
  harness, preserving the prior non-interactive behaviour.
"""

from __future__ import annotations

import argparse
import sys

from cli._errors import print_err
from cli._harness import detect_present, get_adapter
from cli._harness.base import HarnessAdapter


def _parse_indices(answer: str, count: int) -> list[int] | None:
    """Parse ``"1,3"`` / ``"1 3"`` into 0-based indices, or None if bad."""
    tokens = answer.replace(",", " ").split()
    out: list[int] = []
    for tok in tokens:
        if not tok.isdigit():
            return None
        idx = int(tok) - 1
        if idx < 0 or idx >= count:
            return None
        if idx not in out:
            out.append(idx)
    return out


def _prompt_selection(detected: list[HarnessAdapter]) -> list[HarnessAdapter]:
    """Interactively pick a subset of *detected*; empty input → none."""
    print_err("\nDetected agent harnesses:")
    for i, adapter in enumerate(detected, start=1):
        print_err(f"  {i}. {adapter.name}")
    while True:
        # Prompt on stderr (not via input()'s stdout prompt) so --json
        # output on stdout stays machine-readable.
        print_err("Select harness(es) to set up [e.g. 1,3; empty to skip]: ")
        try:
            answer = input().strip()
        except EOFError:
            return []
        if not answer:
            return []
        indices = _parse_indices(answer, len(detected))
        if indices is None:
            print_err("Enter numbers from the list, e.g. 1,3.")
            continue
        return [detected[i] for i in indices]


def select_harnesses(args: argparse.Namespace) -> list[HarnessAdapter]:
    """Resolve the harness adapters to configure during onboarding.

    Returns the resolved adapters (possibly empty). An explicit but
    unknown ``--harness`` is validated earlier by
    ``validate_explicit_harness``; unknown names are dropped here so the
    caller never crashes.
    """
    requested = getattr(args, "harness", None)
    if requested:
        return [
            adapter
            for name in requested
            if (adapter := get_adapter(name)) is not None
        ]

    detected = detect_present()
    if not detected:
        return []
    if not sys.stdin.isatty():
        # Non-interactive: keep configuring every detected harness.
        return detected
    return _prompt_selection(detected)

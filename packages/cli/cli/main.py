# SPDX-License-Identifier: MIT
"""Logion CLI entry point."""

from __future__ import annotations

import os
import sys

from cli._parser import build_parser


def _onboarding_args_from(args):
    """Build a Namespace for the onboarding handler from parsed args.

    Copies common-option fields using the *correct* dest names defined
    by the shared parent parser in ``cli/_options.py`` (``--base-url``
    → ``base_url``, ``--json`` → ``json_output``, ``--max-retries`` →
    ``max_retries``) so first-run onboarding honours the same
    API/output configuration the user passed to the original command.

    Onboarding-specific fields that are absent from the original
    command's parser (e.g. ``autopost_scope``, ``no_companion``) are
    filled with the *onboarding* defaults, not ``None``, so the handler
    never sees an invalid scope or tri-state boolean.

    Defaults are derived from the onboarding subparser itself so a new
    argument added to ``register_onboarding`` propagates automatically
    without a manual mirror list here.

    ``enable_autopost`` is deliberately left at its declared default of
    ``None`` (the tri-state "unset") so first-run onboarding *prompts*
    the user for auto-review consent on a TTY rather than silently
    defaulting it off — auto-review opt-in is a core product decision
    the user must make explicitly, not have made for them.
    """
    import argparse

    from cli._parser import build_parser

    # Build a throwaway parser to harvest the onboarding subparser's
    # declared defaults.  Parse only the subcommand (no overriding
    # flags) so ``enable_autopost`` stays ``None`` → resolve_optin
    # prompts for consent instead of silently disabling auto-review.
    defaults_parser = build_parser()
    base_defaults = defaults_parser.parse_args(["onboarding"])

    namespace = argparse.Namespace()
    for attr in vars(base_defaults):
        if attr == "handler":
            continue
        default_val = getattr(base_defaults, attr)
        setattr(namespace, attr, getattr(args, attr, default_val))

    # Common options — dest names from cli._options.COMMON_PARSER.
    # These arrive via the original command's parser, not the
    # onboarding subparser, so copy them explicitly.
    namespace.api_key = getattr(args, "api_key", None)
    namespace.base_url = getattr(args, "base_url", None)
    namespace.json_output = getattr(args, "json_output", False)
    namespace.timeout = getattr(args, "timeout", None)
    namespace.max_retries = getattr(args, "max_retries", None)
    return namespace


def main(argv: list[str] | None = None) -> int:
    """Parse args and dispatch to the appropriate command handler."""
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(raw)

    from cli._first_run import decide

    decision = decide(raw, args)
    if decision.should_run:
        from cli.commands.identity.onboarding import handle_onboarding

        rc = handle_onboarding(_onboarding_args_from(args))
        if rc != 0:
            return rc

    from cli._auto_update import maybe_auto_update

    if "PYTEST_CURRENT_TEST" not in os.environ:
        maybe_auto_update(args)

    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

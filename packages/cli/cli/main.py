# SPDX-License-Identifier: MIT
"""Logion CLI entry point."""

from __future__ import annotations

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
    """
    import argparse

    namespace = argparse.Namespace()
    # Onboarding-specific fields with their real defaults.
    _defaults: dict[str, object] = {
        "email": None,
        "agent_name": None,
        "user_name": None,
        "password": None,
        "enable_autopost": None,
        "autopost_scope": "global",
        "harness": None,
        "agent_dir": None,
        "companion_source": None,
        "no_companion": False,
        "no_onboarding": False,
    }
    for key, default in _defaults.items():
        setattr(namespace, key, getattr(args, key, default))
    # Common options — dest names from cli._options.COMMON_PARSER.
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

    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

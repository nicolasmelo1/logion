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
    """
    import argparse

    namespace = argparse.Namespace()
    # Onboarding-specific fields.
    for key in (
        "email",
        "agent_name",
        "user_name",
        "password",
        "enable_autopost",
        "autopost_scope",
        "harness",
        "agent_dir",
        "companion_source",
        "no_companion",
        "no_onboarding",
    ):
        setattr(namespace, key, getattr(args, key, None))
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

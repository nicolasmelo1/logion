# SPDX-License-Identifier: MIT
"""Logion CLI entry point."""

from __future__ import annotations

import sys

from cli._parser import build_parser


def _onboarding_args_from(args):
    """Build a Namespace for the onboarding handler from parsed args."""
    import argparse

    namespace = argparse.Namespace()
    # Copy common fields the onboarding handler needs.
    for key in (
        "email", "agent_name", "user_name", "password",
        "enable_autopost", "autopost_scope", "harness",
        "agent_dir", "companion_source", "no_companion",
        "no_onboarding",
    ):
        setattr(namespace, key, getattr(args, key, None))
    # --json / config-related
    namespace.json_output = getattr(args, "json", False)
    namespace.api_url = getattr(args, "api_url", None)
    namespace.api_key = getattr(args, "api_key", None)
    namespace.timeout = getattr(args, "timeout", None)
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

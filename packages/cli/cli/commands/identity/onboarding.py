# SPDX-License-Identifier: MIT
"""``logion identity onboarding`` — one command from zero to ready."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._credentials import save_user_identity, stored_user_id
from cli._errors import handle_error, print_err
from cli._harness import adapter_names
from cli._output import emit_json

from . import _autopost
from ._closing_copy import CLOSING_COPY, ONBOARDING_NEXT_STEPS
from ._onboarding_helpers import run_companion_step, validate_explicit_harness
from .handlers import API_KEY_WARNING, _field, _resolve_password


def _prompt(question: str, default: str | None = None) -> str:
    """Prompt for free text; return *default* on empty input."""
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{question}{suffix}: ").strip()
    except EOFError:
        return default or ""
    return answer or (default or "")


def _resolve_email(cli_value: str | None) -> str | None:
    """Return the email from the flag, an interactive prompt, or None."""
    if cli_value:
        return cli_value
    if sys.stdin.isatty():
        email = _prompt("Email")
        return email or None
    print_err("Error: --email is required in non-interactive mode.")
    return None


def _provision_identity(
    args: argparse.Namespace,
    config: object,
) -> dict[str, object] | None:
    """Create a user + first agent and persist identity context.

    Returns a summary dict (including the one-time API key), or ``None``
    on a handled error.
    """
    email = _resolve_email(args.email)
    if email is None:
        return None

    agent_name = args.agent_name
    if not agent_name:
        agent_name = (
            _prompt("Agent name", default="default-agent")
            if sys.stdin.isatty()
            else "default-agent"
        )

    password = _resolve_password(args.password)
    if password is None:
        return None

    client = make_client(config)  # type: ignore[arg-type]
    try:
        result = client.v1.identity.create_user_with_agent(
            email=email,
            user_password=password,
            agent_name=agent_name,
            user_name=args.user_name,
            agent_description=None,
        )
    except Exception as exc:
        handle_error(exc)
        return None
    finally:
        client.close()

    user = _field(result, "user")
    agent = _field(result, "agent")
    user_id = _field(user, "id")
    agent_id = _field(agent, "id")
    resolved_email = _field(user, "email")

    if user_id is not None:
        try:
            save_user_identity(
                str(user_id),
                email=str(resolved_email)
                if resolved_email is not None
                else None,
                agent_id=str(agent_id) if agent_id is not None else None,
            )
        except OSError as exc:
            print_err(f"Warning: could not save credentials: {exc}")

    print_err(API_KEY_WARNING)
    return {
        "user_id": str(user_id) if user_id is not None else None,
        "agent_id": str(agent_id) if agent_id is not None else None,
        "email": str(resolved_email) if resolved_email is not None else None,
        "api_key": _field(result, "api_key"),
        "api_key_prefix": _field(result, "api_key_prefix"),
        "created": True,
    }


def handle_onboarding(args: argparse.Namespace) -> int:
    """Execute the identity onboarding command."""
    config = resolve_config_from_args(args)
    summary: dict[str, object] = {}

    existing = stored_user_id()
    if existing is None:
        identity = _provision_identity(args, config)
        if identity is None:
            return 2
        summary.update(identity)
    else:
        print_err(f"Already onboarded (user {existing}).")
        summary.update({"user_id": existing, "created": False})

    # Validate an explicitly-requested harness up-front so an unknown
    # name is a hard error before autopost or the companion step runs.
    rc = validate_explicit_harness(args)
    if rc is not None:
        return rc

    if _autopost.resolve_optin(args):
        autopost = _autopost.apply(args)
        if autopost is None:
            return 2
        summary["autopost"] = autopost
    else:
        print_err(
            "Auto-review not enabled. Enable later with "
            "`logion identity onboarding --enable-autopost`."
        )
        summary["autopost"] = {"enabled": False}

    companion_summary, rc = run_companion_step(args)
    if rc is not None:
        return rc
    summary["companion"] = companion_summary

    print_err(CLOSING_COPY)

    if config.json_output:
        # Stable machine-readable next steps so agents can drive the
        # marketplace loop without parsing human-readable copy.
        summary["next_steps"] = ONBOARDING_NEXT_STEPS
        emit_json("logion.identity.onboarding", summary)
    return 0


def register_onboarding(sub: argparse._SubParsersAction) -> None:
    """Register the ``identity onboarding`` subcommand."""
    from cli._options import COMMON_PARSER

    parser = sub.add_parser(
        "onboarding",
        help="Set up user, agent, and (optionally) auto-review in one step",
        parents=[COMMON_PARSER],
    )
    parser.add_argument("--email", help="Email for the new user.")
    parser.add_argument("--agent-name", help="Name for the first agent.")
    parser.add_argument("--user-name", help="Display name (optional).")
    parser.add_argument(
        "--password",
        help=(
            "User credential (passing it on the CLI is unsafe — leaves "
            "shell history; omit to use a hidden interactive prompt)"
        ),
    )
    autopost = parser.add_mutually_exclusive_group()
    autopost.add_argument(
        "--enable-autopost",
        action="store_true",
        default=None,
        dest="enable_autopost",
        help="Allow agents to auto-post usage reviews (writes a "
        "harness permission rule).",
    )
    autopost.add_argument(
        "--no-enable-autopost",
        action="store_false",
        default=None,
        dest="enable_autopost",
        help="Do not enable auto-review (and revoke nothing).",
    )
    parser.add_argument(
        "--autopost-scope",
        choices=["project", "global"],
        default="global",
        help="Where to write the permission (default: global).",
    )
    parser.add_argument(
        "--harness",
        default=None,
        help=(
            "Target a specific harness (default: auto-detect). "
            f"Supported: {', '.join(adapter_names())}."
        ),
    )
    parser.add_argument(
        "--agent-dir",
        default=None,
        help="Write the companion into this skill dir (a CustomPathHarness). "
        "Overrides --harness detection for the companion step.",
    )
    parser.add_argument(
        "--companion-source",
        type=Path,
        default=None,
        help="Companion bundle source directory (default: auto-locate).",
    )
    parser.add_argument(
        "--no-companion",
        action="store_true",
        help="Skip the companion install/sync step.",
    )
    # ``--no-onboarding`` is inherited from COMMON_PARSER; no need to
    # re-declare it here.
    parser.set_defaults(handler=handle_onboarding)

# SPDX-License-Identifier: MIT
"""``logion identity onboarding`` — one command from zero to ready."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli._config import resolve_config_from_args
from cli._credentials import (
    stored_agent_id,
    stored_api_key,
    stored_api_key_prefix,
    stored_user_id,
)
from cli._errors import print_err
from cli._harness import adapter_names
from cli._json import JsonObject
from cli._output import emit_json

from . import _autopost
from ._api_keys import rotate_and_save_api_key
from ._closing_copy import CLOSING_COPY, ONBOARDING_NEXT_STEPS
from ._harness_select import select_harnesses
from ._onboarding_helpers import (
    run_companion_step,
    validate_explicit_harness,
)
from ._provisioning import provision_identity
from ._setup_token import redeem_setup_token, resolve_setup_token
from .handlers import _resolve_password

_MSG_MISSING_KEY = "Stored Logion API key missing; repairing credentials."


def _repair_missing_api_key(
    args: argparse.Namespace,
    config: object,
    user_id: str,
) -> JsonObject | None:
    """Persist an API key for legacy onboarding runs that
    saved only ids."""
    agent_id = stored_agent_id()
    if agent_id is None:
        print_err(
            "Warning: no stored agent id; run "
            "`logion identity agents-add` or re-onboard "
            "with a fresh identity."
        )
        return {"api_key_persisted": False}

    password = _resolve_password(args.password)
    if password is None:
        return {"api_key_persisted": False}
    return rotate_and_save_api_key(config, user_id, agent_id, password)


def _handle_standard_path(
    args: argparse.Namespace,
    config: object,
    summary: JsonObject,
) -> int | None:
    """Run the interactive email/password onboarding path.

    Returns an exit code on failure, or ``None`` on success.
    """
    existing = stored_user_id()
    if existing is None:
        identity = provision_identity(args, config)
        if identity is None:
            return 2
        summary.update(identity)
        return None

    print_err(f"Already onboarded (user {existing}).")
    summary.update({"user_id": existing, "created": False})
    existing_api_key = stored_api_key()
    if existing_api_key is None:
        print_err(_MSG_MISSING_KEY)
        repaired = _repair_missing_api_key(args, config, existing)
        if repaired is None:
            return 2
        summary["credentials"] = repaired
    else:
        summary["credentials"] = {
            "api_key_persisted": True,
            "api_key_prefix": stored_api_key_prefix(),
        }
    return None


def handle_onboarding(args: argparse.Namespace) -> int:
    """Execute the identity onboarding command."""
    config = resolve_config_from_args(args)
    summary: JsonObject = {}

    # --- Setup-token path: non-interactive, no email/password ---
    setup_token = resolve_setup_token(args)
    if setup_token:
        existing = stored_user_id()
        if existing is not None:
            print_err(
                "Refusing to overwrite stored credentials with a setup token. "
                "Remove existing Logion credentials first or use a fresh "
                "machine."
            )
            return 2
        result = redeem_setup_token(args, config, setup_token)
        if result is None:
            return 2
        summary.update(result)
    else:
        rc = _handle_standard_path(args, config, summary)
        if rc is not None:
            return rc

    # Validate an explicitly-requested harness up-front so an unknown
    # name is a hard error before autopost or the companion step runs.
    rc = validate_explicit_harness(args)
    if rc is not None:
        return rc

    # Decide auto-review first, then resolve the harness(es) once
    # and share that choice between the grant and the companion
    # install.  Only prompt for a harness when a step actually needs
    # one — skip it entirely when auto-review is off and --no-companion
    # is set.
    autopost_enabled = _autopost.resolve_optin(args)
    companion_will_run = not getattr(args, "no_companion", False)

    if autopost_enabled or companion_will_run:
        adapters = select_harnesses(args)
    else:
        adapters = []

    if autopost_enabled:
        autopost = _autopost.apply(args, adapters)
        if autopost is None:
            return 2
        summary["autopost"] = autopost
    else:
        print_err(
            "Auto-review not enabled. Enable later with "
            "`logion identity onboarding --enable-autopost`."
        )
        summary["autopost"] = {"enabled": False}

    companion_summary, rc = run_companion_step(args, adapters)
    if rc is not None:
        return rc
    summary["companion"] = companion_summary

    print_err(CLOSING_COPY)

    if config.json_output:  # type: ignore[attr-defined]
        # Stable machine-readable next steps so agents can drive
        # the marketplace loop without parsing human-readable copy.
        summary["next_steps"] = ONBOARDING_NEXT_STEPS
        emit_json("logion.identity.onboarding", summary)
    return 0


def register_onboarding(
    sub: argparse._SubParsersAction,
) -> None:
    """Register the ``identity onboarding`` subcommand."""
    from cli._options import COMMON_PARSER

    parser = sub.add_parser(
        "onboarding",
        help="Set up user, agent, and (optionally) auto-review in one step",
        parents=[COMMON_PARSER],
    )
    parser.add_argument("--email", help="Email for the new user.")
    parser.add_argument(
        "--agent-name",
        help="Name for the first agent.",
    )
    parser.add_argument("--user-name", help="Display name (optional).")
    parser.add_argument(
        "--password",
        help=(
            "User credential (passing it on the CLI is "
            "unsafe — leaves shell history; omit to use "
            "a hidden interactive prompt)"
        ),
    )
    autopost = parser.add_mutually_exclusive_group()
    autopost.add_argument(
        "--enable-autopost",
        action="store_true",
        default=None,
        dest="enable_autopost",
        help="Allow agents to auto-post usage reviews "
        "(writes a harness permission rule).",
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
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Target a specific harness; repeat for several "
            "(e.g. --harness claude-code --harness codex). "
            "Omit in an interactive terminal to pick from "
            "detected harnesses. "
            f"Supported: {', '.join(adapter_names())}."
        ),
    )
    parser.add_argument(
        "--agent-dir",
        default=None,
        help="Write the companion into this skill dir "
        "(a CustomPathHarness). "
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
    parser.add_argument(
        "--setup-token",
        default=None,
        help="One-time setup token from GitHub sign-in "
        "(bypasses email/password prompts). "
        "Also read from LOGION_SETUP_TOKEN.",
    )
    # ``--no-onboarding`` is inherited from COMMON_PARSER; no need
    # to re-declare it here.
    parser.set_defaults(handler=handle_onboarding)

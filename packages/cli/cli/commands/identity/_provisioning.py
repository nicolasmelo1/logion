# SPDX-License-Identifier: MIT
"""Provision the first Logion user and agent during onboarding."""

from __future__ import annotations

import argparse
import sys

from cli._context import make_client
from cli._credentials import save_user_identity
from cli._errors import handle_error, print_err
from cli._json import JsonObject
from cli.commands.identity._fields import field

from ._api_keys import api_key_parts
from .handlers import API_KEY_WARNING, _resolve_password


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


def provision_identity(
    args: argparse.Namespace,
    config: object,
) -> JsonObject | None:
    """Create a user + first agent and persist identity context."""
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

    user = field(result, "user")
    agent = field(result, "agent")
    user_id = field(user, "id")
    agent_id = field(agent, "id")
    resolved_email = field(user, "email")
    api_key, api_key_prefix = api_key_parts(result)

    if user_id is not None:
        try:
            save_user_identity(
                str(user_id),
                email=str(resolved_email)
                if resolved_email is not None
                else None,
                agent_id=str(agent_id) if agent_id is not None else None,
                api_key=api_key,
                api_key_prefix=api_key_prefix,
            )
        except OSError as exc:
            print_err(f"Warning: could not save credentials: {exc}")

    print_err(API_KEY_WARNING)
    return {
        "user_id": str(user_id) if user_id is not None else None,
        "agent_id": str(agent_id) if agent_id is not None else None,
        "email": str(resolved_email) if resolved_email is not None else None,
        "api_key": field(result, "api_key"),
        "api_key_prefix": field(result, "api_key_prefix"),
        "created": True,
    }

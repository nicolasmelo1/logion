"""Handlers for identity commands."""

from __future__ import annotations

import argparse
import os

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, print_err
from cli._output import emit

API_KEY_WARNING = (
    "Important: save the API key now — it will not be shown again."
)


def _resolve_password(cli_value: str | None) -> str | None:
    """Return the resolved password, or ``None`` on validation failure."""
    if cli_value is not None:
        if not cli_value.strip():
            print_err("Error: --password must not be empty.")
            return None
        if cli_value != cli_value.strip():
            print_err(
                "Warning: --password has leading/trailing whitespace — "
                "this is intentional, but may be a shell quoting mistake."
            )
        return cli_value
    raw_env = os.environ.get("LOGION_PASSWORD")
    if raw_env is not None:
        if not raw_env.strip():
            print_err("Error: LOGION_PASSWORD is set but empty/whitespace.")
            return None
        if raw_env != raw_env.strip():
            print_err(
                "Warning: LOGION_PASSWORD has leading/trailing whitespace — "
                "this is intentional, but may be an environment setup mistake."
            )
        return raw_env
    print_err("Error: --password is required (or set LOGION_PASSWORD).")
    return None


def handle_users_create(args: argparse.Namespace) -> int:
    """Execute the identity users-create command."""
    password = _resolve_password(args.password)
    if password is None:
        return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.identity.create_user_with_agent(
            email=args.email,
            user_password=password,
            agent_name=args.agent_name,
            user_name=args.user_name,
            agent_description=args.agent_description,
        )
        print_err(API_KEY_WARNING)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_agents_add(args: argparse.Namespace) -> int:
    """Execute the identity agents-add command."""
    password = _resolve_password(args.password)
    if password is None:
        return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.identity.add_agent_to_user(
            user_id=args.user_id,
            agent_name=args.agent_name,
            user_password=password,
            agent_description=args.agent_description,
        )
        print_err(API_KEY_WARNING)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_agents_rotate_key(args: argparse.Namespace) -> int:
    """Execute the identity agents-rotate-key command."""
    password = _resolve_password(args.password)
    if password is None:
        return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.identity.rotate_api_key(
            user_id=args.user_id,
            agent_id=args.agent_id,
            user_password=password,
        )
        print_err(API_KEY_WARNING)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

# SPDX-License-Identifier: MIT
"""Handlers for identity commands."""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._credentials import save_user_identity, stored_user_id
from cli._errors import handle_error, print_err
from cli._output import emit
from cli.commands.identity._fields import field

from ._api_keys import api_key_parts, save_api_key

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
    if sys.stdin.isatty():
        password = getpass.getpass("Logion Password: ")
        if not password.strip():
            print_err("Error: password must not be empty.")
            return None
        return password
    print_err(
        "Error: password is required in non-interactive mode "
        "(use --password or set LOGION_PASSWORD)."
    )
    return None


def _save_user_identity_from_result(result: object) -> None:
    """Persist the created user's id/email; never fail the command."""
    user = field(result, "user")
    if user is None:
        return
    user_id = field(user, "id")
    if user_id is None:
        return
    email = field(user, "email")
    agent = field(result, "agent")
    agent_id = field(agent, "id") if agent is not None else None
    api_key, api_key_prefix = api_key_parts(result)
    try:
        save_user_identity(
            str(user_id),
            email=str(email) if email is not None else None,
            agent_id=str(agent_id) if agent_id is not None else None,
            api_key=api_key,
            api_key_prefix=api_key_prefix,
        )
    except OSError as exc:
        print_err(f"Warning: could not save credentials: {exc}")


def _save_rotated_key_from_result(
    user_id: str,
    agent_id: str,
    result: object,
) -> None:
    """Persist a newly rotated API key; never fail the command."""
    save_api_key(user_id, agent_id, result)


def _resolve_user_id(cli_value: str | None) -> str | None:
    """Return ``--user-id`` or the stored credential, ``None`` if neither."""
    if cli_value is not None:
        return cli_value
    stored = stored_user_id()
    if stored is not None:
        return stored
    print_err(
        "Error: --user-id is required (no stored user found — run "
        "`logion identity users-create` or pass --user-id)."
    )
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
        _save_user_identity_from_result(result)
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
    user_id = _resolve_user_id(args.user_id)
    if user_id is None:
        return 2
    password = _resolve_password(args.password)
    if password is None:
        return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.identity.add_agent_to_user(
            user_id=user_id,
            agent_name=args.agent_name,
            user_password=password,
            agent_description=args.agent_description,
        )
        _save_user_identity_from_result(result)
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
    user_id = _resolve_user_id(args.user_id)
    if user_id is None:
        return 2
    password = _resolve_password(args.password)
    if password is None:
        return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.identity.rotate_api_key(
            user_id=user_id,
            agent_id=args.agent_id,
            user_password=password,
        )
        _save_rotated_key_from_result(user_id, args.agent_id, result)
        print_err(API_KEY_WARNING)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()

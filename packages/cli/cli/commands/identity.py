"""Identity commands — user and agent onboarding."""

from __future__ import annotations

import argparse
import os

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, print_err
from cli._options import COMMON_PARSER
from cli._output import emit


def _resolve_password(cli_value: str | None) -> str | None:
    """Return the resolved password, or ``None`` on validation failure.

    Checks CLI arg first, then ``LOGION_PASSWORD`` env var.
    Explicitly provided but empty/whitespace-only values are rejected
    outright — they do *not* fall through to the env var.
    Whitespace is stripped only for the emptiness check; the actual
    password value is returned verbatim — passwords are opaque and
    must not be mutated.
    """
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
        return raw_env
    print_err("Error: --password is required (or set LOGION_PASSWORD).")
    return None


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``identity`` subcommand group."""
    parser = subparsers.add_parser(
        "identity",
        help="Manage users and agents",
    )
    sub = parser.add_subparsers(
        dest="identity_command",
        required=True,
    )

    # ── users create ────────────────────────────────────────────
    uc = sub.add_parser(
        "users-create",
        help="Create a user with a first agent",
        parents=[COMMON_PARSER],
    )
    uc.add_argument("--email", required=True)
    uc.add_argument(
        "--password",
        help=(
            "Password (passing on the CLI is unsafe — "
            "leaves shell history; prefer the LOGION_PASSWORD env var)"
        ),
    )
    uc.add_argument("--agent-name", required=True)
    uc.add_argument("--user-name")
    uc.add_argument("--agent-description")
    uc.set_defaults(handler=handle_users_create)

    # ── agents add ──────────────────────────────────────────────
    aa = sub.add_parser(
        "agents-add",
        help="Add an agent to an existing user",
        parents=[COMMON_PARSER],
    )
    aa.add_argument("--user-id", required=True)
    aa.add_argument("--agent-name", required=True)
    aa.add_argument(
        "--password",
        help=(
            "Password (passing on the CLI is unsafe — "
            "leaves shell history; prefer the LOGION_PASSWORD env var)"
        ),
    )
    aa.add_argument("--agent-description")
    aa.set_defaults(handler=handle_agents_add)

    # ── agents rotate-key ───────────────────────────────────────
    rk = sub.add_parser(
        "agents-rotate-key",
        help="Rotate an agent API key",
        parents=[COMMON_PARSER],
    )
    rk.add_argument("--user-id", required=True)
    rk.add_argument("--agent-id", required=True)
    rk.add_argument(
        "--password",
        help=(
            "Password (passing on the CLI is unsafe — "
            "leaves shell history; prefer the LOGION_PASSWORD env var)"
        ),
    )
    rk.set_defaults(handler=handle_agents_rotate_key)


_API_KEY_WARNING = (
    "Important: save the API key now — it will not be shown again."
)


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
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        print_err(_API_KEY_WARNING)
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
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        print_err(_API_KEY_WARNING)
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
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        print_err(_API_KEY_WARNING)
        return 0
    finally:
        client.close()

# SPDX-License-Identifier: MIT
"""``logion identity github`` — connect, status, disconnect."""

from __future__ import annotations

import argparse
import time

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import emit_error_json, handle_error, print_err
from cli._output import emit_json, to_data
from logion import APIError

_CONNECT_KIND = "logion.identity.github.connect"
_STATUS_KIND = "logion.identity.github.status"
_DISCONNECT_KIND = "logion.identity.github.disconnect"
_MAX_DEVICE_FLOW_EXPIRES_IN_S = 900
_MAX_DEVICE_FLOW_SLEEP_S = 30


def _require_yes(yes: bool, action: str, json_output: bool) -> int | None:
    """Return ``None`` if *yes* is set, else exit code 2."""
    if yes:
        return None
    message = f"This is a destructive action. Re-run with --yes to {action}."
    if json_output:
        emit_error_json("confirmation_required", message, 2)
    else:
        print_err(message)
    return 2


def _detail_text(detail: str | list[dict[str, object]]) -> str:
    if isinstance(detail, list):
        return "; ".join(str(item) for item in detail)
    return str(detail)


def _api_error_code(exc: APIError) -> str:
    detail_text = _detail_text(exc.detail).lower()
    if exc.status_code == 401:
        return "auth_missing"
    if "github_oauth_unconfigured" in detail_text or exc.status_code == 503:
        return "github_oauth_unconfigured"
    if "github_identity_conflict" in detail_text or exc.status_code == 409:
        return "github_identity_conflict"
    if exc.status_code == 404:
        return "not_found"
    if exc.status_code == 422:
        return "validation_failed"
    return "server_error"


def _handle_api_error(exc: APIError, json_output: bool) -> int:
    if json_output:
        emit_error_json(_api_error_code(exc), _detail_text(exc.detail), 1)
    else:
        return handle_error(exc)
    return 1


def handle_connect(args: argparse.Namespace) -> int:
    """Execute ``identity github connect`` via device flow."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        begin = client.v1.identity.begin_github_device_flow(
            scope_tier=args.scope_tier,
        )
        user_code = begin.user_code
        verification_uri = begin.verification_uri
        device_code = begin.device_code
        interval = max(begin.interval, 1)
        expires_in = min(
            max(begin.expires_in, 1), _MAX_DEVICE_FLOW_EXPIRES_IN_S
        )

        if config.json_output:
            emit_json(
                _CONNECT_KIND,
                {
                    "phase": "device_code",
                    "user_code": user_code,
                    "verification_uri": verification_uri,
                    "expires_in": expires_in,
                    "interval": interval,
                },
            )
        else:
            print(f"Open {verification_uri} and enter code: {user_code}")
            print(f"Waiting for authorization (expires in {expires_in}s)...")

        deadline = time.monotonic() + expires_in
        while time.monotonic() < deadline:
            remaining = max(deadline - time.monotonic(), 0.0)
            sleep_for = min(interval, remaining, _MAX_DEVICE_FLOW_SLEEP_S)
            if sleep_for > 0:
                time.sleep(sleep_for)
            result = client.v1.identity.poll_github_device_flow(
                device_code=device_code,
                scope_tier=args.scope_tier,
            )
            status = getattr(result, "status", None)
            if status == "pending":
                interval = max(getattr(result, "interval", interval), 1)
                continue
            data = to_data(result)
            if config.json_output:
                emit_json(_CONNECT_KIND, data)
            else:
                login = getattr(result, "github_login", "?")
                print(f"Connected as @{login}")
            return 0

        if config.json_output:
            emit_error_json(
                "github_device_flow_timeout",
                "Device flow timed out.",
                2,
            )
        else:
            print_err("Device flow timed out before authorization completed.")
    except APIError as exc:
        return _handle_api_error(exc, config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 2
    finally:
        client.close()


def handle_status(args: argparse.Namespace) -> int:
    """Execute ``identity github status``."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.identity.get_github_identity()
        data = to_data(result)
        if config.json_output:
            emit_json(_STATUS_KIND, data)
        else:
            connected = data.get("connected", False)
            login = data.get("github_login")
            if connected:
                print(f"Connected as @{login}")
            else:
                print("Not connected")
    except APIError as exc:
        return _handle_api_error(exc, config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_disconnect(args: argparse.Namespace) -> int:
    """Execute ``identity github disconnect``."""
    config = resolve_config_from_args(args)
    refusal = _require_yes(
        args.yes,
        "disconnect your GitHub identity",
        config.json_output,
    )
    if refusal is not None:
        return refusal
    client = make_client(config)
    try:
        result = client.v1.identity.revoke_github_identity()
        data = to_data(result) if not isinstance(result, dict) else result
        if config.json_output:
            emit_json(_DISCONNECT_KIND, data)
        else:
            print("GitHub identity disconnected.")
    except APIError as exc:
        return _handle_api_error(exc, config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def register_github(sub: argparse._SubParsersAction) -> None:
    """Register the ``identity github`` subgroup."""
    github = sub.add_parser(
        "github",
        help="Manage GitHub identity connection",
    )
    github_sub = github.add_subparsers(
        dest="identity_github_command",
        required=True,
    )

    connect = github_sub.add_parser(
        "connect",
        help="Connect GitHub via device flow",
        parents=_common(),
    )
    connect.add_argument(
        "--scope-tier",
        choices=["identity", "repo"],
        default="identity",
    )
    connect.set_defaults(handler=handle_connect)

    status = github_sub.add_parser(
        "status",
        help="Show GitHub connection status",
        parents=_common(),
    )
    status.set_defaults(handler=handle_status)

    disconnect = github_sub.add_parser(
        "disconnect",
        help="Disconnect GitHub identity",
        parents=_common(),
    )
    disconnect.add_argument("--yes", action="store_true")
    disconnect.set_defaults(handler=handle_disconnect)


def _common() -> list[argparse.ArgumentParser]:
    """Return the common parent parser list for github subcommands."""
    from cli._options import COMMON_PARSER

    return [COMMON_PARSER]

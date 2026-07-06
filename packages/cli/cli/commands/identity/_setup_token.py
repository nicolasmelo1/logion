# SPDX-License-Identifier: MIT
"""Redeem a one-time setup token from GitHub sign-in.

When a setup token is present the onboarding flow is fully
non-interactive: no email/password prompts, no consent prompts.
The token is exchanged for an agent + API key in a single API call,
credentials are persisted, and the companion-install + closing-copy
steps continue unchanged.
"""

from __future__ import annotations

import argparse
import os

from cli._context import make_client
from cli._credentials import save_user_identity
from cli._errors import handle_error, print_err

# The logion.sh URL shown to the user when a token is expired or
# already redeemed, so they can mint a fresh one.
_MINT_URL = "https://logion.sh/v1/setup/github/start"


def resolve_setup_token(args: argparse.Namespace) -> str | None:
    """Return the setup token from the CLI flag or env var.

    The ``--setup-token`` flag wins over ``LOGION_SETUP_TOKEN``.
    """
    explicit = getattr(args, "setup_token", None)
    if explicit:
        return explicit
    return os.getenv("LOGION_SETUP_TOKEN") or None


def redeem_setup_token(
    args: argparse.Namespace,
    config: object,
    token: str,
) -> dict[str, object] | None:
    """Redeem a setup token and persist the resulting credentials.

    Returns a summary dict on success, or ``None`` on failure (caller
    should exit with code 2).
    """
    agent_name = getattr(args, "agent_name", None) or "default-agent"
    agent_description = getattr(args, "agent_description", None)

    client = make_client(config)  # type: ignore[arg-type]
    try:
        result = client.v1.setup_tokens.redeem(
            setup_token=token,
            agent_name=agent_name,
            agent_description=agent_description,
        )
    except Exception as exc:
        # Map 410 (expired) and 409 (already redeemed) to a
        # specific error code so the installer can surface a
        # clear message.
        status = getattr(exc, "status_code", None)
        if status in (409, 410):
            print_err(
                "Setup token is invalid or expired. "
                f"Get a new one at: {_MINT_URL}"
            )
            return None
        handle_error(exc)
        return None
    finally:
        client.close()

    # Extract response fields.
    user_id = _field(result, "user_id")
    agent_id = _field(result, "agent_id")
    api_key = _field(result, "api_key")
    api_key_prefix = _field(result, "api_key_prefix")

    if user_id is not None:
        try:
            save_user_identity(
                str(user_id),
                agent_id=(str(agent_id) if agent_id is not None else None),
                api_key=(str(api_key) if api_key is not None else None),
                api_key_prefix=(
                    str(api_key_prefix) if api_key_prefix is not None else None
                ),
            )
        except OSError as exc:
            print_err(f"Warning: could not save credentials: {exc}")

    # Token flow never grants auto-review consent.
    print_err(
        "Auto-review not enabled. Enable later with "
        "`logion identity onboarding --enable-autopost`."
    )

    return {
        "user_id": (str(user_id) if user_id is not None else None),
        "agent_id": (str(agent_id) if agent_id is not None else None),
        "api_key": api_key,
        "api_key_prefix": api_key_prefix,
        "autoreview_consent": False,
        "created": True,
        "path": "github_setup_token",
    }


def _field(data: dict[str, object] | object, key: str) -> object | None:
    """Extract a field from an SDK response object or plain dict."""
    if isinstance(data, dict):
        return data.get(key)
    return getattr(data, key, None)

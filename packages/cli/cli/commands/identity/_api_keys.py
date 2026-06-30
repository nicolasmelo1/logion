# SPDX-License-Identifier: MIT
"""Persist agent API keys returned by identity operations."""

from __future__ import annotations

from cli._context import make_client
from cli._credentials import save_user_identity
from cli._errors import handle_error, print_err


def field(obj: object, name: str) -> object:
    """Read *name* from a dict or attribute-style response object."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def api_key_parts(result: object) -> tuple[str | None, str | None]:
    """Return the API key value and prefix from an identity response."""
    api_key = field(result, "api_key")
    if api_key is None:
        return None, None
    if isinstance(api_key, str):
        return api_key, None
    key = field(api_key, "key")
    prefix = field(api_key, "prefix")
    return (
        str(key) if key is not None else None,
        str(prefix) if prefix is not None else None,
    )


def save_api_key(
    user_id: str,
    agent_id: str | None,
    result: object,
) -> dict[str, object]:
    """Persist an API key from an identity response."""
    api_key, api_key_prefix = api_key_parts(result)
    if api_key is None:
        print_err("Warning: identity API did not return an API key.")
        return {"api_key_persisted": False}
    try:
        save_user_identity(
            user_id,
            agent_id=agent_id,
            api_key=api_key,
            api_key_prefix=api_key_prefix,
        )
    except OSError as exc:
        print_err(f"Warning: could not save credentials: {exc}")
        return {"api_key_persisted": False}
    return {"api_key_persisted": True, "api_key_prefix": api_key_prefix}


def rotate_and_save_api_key(
    config: object,
    user_id: str,
    agent_id: str,
    password: str,
) -> dict[str, object] | None:
    """Rotate an agent API key and persist it."""
    client = make_client(config)  # type: ignore[arg-type]
    try:
        result = client.v1.identity.rotate_api_key(
            user_id=user_id,
            agent_id=agent_id,
            user_password=password,
        )
    except Exception as exc:
        handle_error(exc)
        return None
    finally:
        client.close()
    summary = save_api_key(user_id, agent_id, result)
    if summary["api_key_persisted"]:
        print_err("Saved Logion agent API key for future commands.")
    return summary

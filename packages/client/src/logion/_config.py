# SPDX-License-Identifier: MIT
"""Client configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://api.logion.sh"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3


def resolve_env_or(key: str, default: str) -> str:
    """Return *os.environ[key]* if set, otherwise *default*."""
    return os.environ.get(key, default)


@dataclass
class ClientConfig:
    """Resolved configuration for the Logion HTTP client."""

    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    extra_headers: dict[str, str] = field(default_factory=dict)


def resolve_config(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    extra_headers: dict[str, str] | None = None,
) -> ClientConfig:
    """Resolve SDK configuration from explicit values, env vars, or
    defaults — in that priority order."""
    return ClientConfig(
        base_url=(
            base_url
            if base_url is not None
            else resolve_env_or("LOGION_BASE_URL", DEFAULT_BASE_URL)
        ),
        api_key=(
            api_key
            if api_key is not None
            else resolve_env_or("LOGION_API_KEY", "")
        ),
        timeout=timeout if timeout is not None else DEFAULT_TIMEOUT,
        max_retries=(
            max_retries if max_retries is not None else DEFAULT_MAX_RETRIES
        ),
        extra_headers=extra_headers if extra_headers is not None else {},
    )

"""Client configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://api.logion.dev"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3


def _env(key: str, default: str) -> str:
    """Read a value from environment, falling back to *default*."""
    return os.environ.get(key, default)


@dataclass
class ClientConfig:
    """Configuration for the Logion client."""

    base_url: str = field(
        default_factory=lambda: _env("LOGION_BASE_URL", DEFAULT_BASE_URL)
    )
    api_key: str = field(default_factory=lambda: _env("LOGION_API_KEY", ""))
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    extra_headers: dict[str, str] = field(default_factory=dict)

"""Client configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://api.logion.dev"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3


@dataclass
class ClientConfig:
    """Configuration for the Logion client."""

    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    extra_headers: dict[str, str] = field(default_factory=dict)

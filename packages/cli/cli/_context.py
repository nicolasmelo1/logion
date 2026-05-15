"""CLI context — builds a LogionClient from CliConfig."""

from __future__ import annotations

from cli._config import CliConfig
from logion import LogionClient


def make_client(config: CliConfig) -> LogionClient:
    """Create a LogionClient from resolved CLI configuration."""
    return LogionClient(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )

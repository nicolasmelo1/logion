# SPDX-License-Identifier: MIT
"""CLI configuration — env-var resolution and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.logion.sh"


@dataclass(frozen=True)
class CliConfig:
    """Resolved CLI configuration."""

    api_key: str | None
    base_url: str
    json_output: bool
    timeout: float | None
    max_retries: int | None


def is_truthy(value: str | None) -> bool:
    """Return True if *value* looks like a truthy env-var string."""
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


def is_admin_enabled() -> bool:
    """Return True if ``LOGION_ENABLE_ADMIN`` is set to a truthy value."""
    return is_truthy(os.getenv("LOGION_ENABLE_ADMIN"))


def resolve_config_from_args(
    args: object,
) -> CliConfig:
    """Build a CliConfig from parsed argparse args + env vars."""
    api_key: str | None = getattr(args, "api_key", None)
    if api_key is None:
        api_key = os.getenv("LOGION_API_KEY")

    base_url: str | None = getattr(args, "base_url", None)
    if base_url is None:
        base_url = os.getenv("LOGION_BASE_URL", DEFAULT_BASE_URL)

    return CliConfig(
        api_key=api_key,
        base_url=base_url,
        json_output=getattr(args, "json_output", False),
        timeout=getattr(args, "timeout", None),
        max_retries=getattr(args, "max_retries", None),
    )

# SPDX-License-Identifier: MIT
"""CLI context — builds a LogionClient from CliConfig."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cli._config import CliConfig
from cli._lazy_import import LazyModule

if TYPE_CHECKING:
    import logion
else:
    logion = LazyModule("logion")


class _LogionClientFactory:
    def __call__(self, **kwargs: Any) -> logion.LogionClient:
        return logion.LogionClient(**kwargs)


# Keep the existing monkeypatch seam without importing the SDK at startup.
LogionClient = _LogionClientFactory()


def make_client(config: CliConfig) -> logion.LogionClient:
    """Create a LogionClient from resolved CLI configuration."""
    return LogionClient(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )

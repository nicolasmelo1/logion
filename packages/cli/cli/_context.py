# SPDX-License-Identifier: MIT
"""CLI context — builds a LogionClient from CliConfig."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cli._config import CliConfig
from cli._lazy_import import LazyModule

if TYPE_CHECKING:
    import logion
else:
    logion = LazyModule("logion")


class _LogionClientFactory:
    """Construct the SDK client without importing it at startup.

    Spelled out rather than ``**kwargs``: this is the seam tests
    monkeypatch, so the parameters it accepts are part of the contract
    and worth stating.
    """

    def __call__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> logion.LogionClient:
        return logion.LogionClient(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )


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

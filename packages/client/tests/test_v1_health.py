"""Tests for the v1.health resource."""

from __future__ import annotations

import pytest

from logion import LogionClient


@pytest.fixture
def unauthenticated_client() -> LogionClient:
    """Client without API key (health endpoint needs no auth)."""
    c = LogionClient(
        base_url="http://localhost:4010",
        max_retries=0,
    )
    yield c
    c.close()


# NOTE: These tests require a running Prism mock server on port 4010.
# Run ``make -C packages/client mock-server`` from the workspace root,
# or skip them in CI where Prism is started as a service.


@pytest.mark.integration
class TestHealthCheck:
    """Integration tests for HealthResource."""

    def test_health_check_returns_ok(
        self, unauthenticated_client: LogionClient
    ) -> None:
        """GET /health returns a dict with a status key."""
        result = unauthenticated_client.v1.health.check()
        assert isinstance(result, dict)
        assert "status" in result

"""Shared test fixtures for the Logion client SDK."""

from __future__ import annotations

import pytest

from logion import LogionClient

MOCK_BASE_URL = "http://localhost:4010"
MOCK_API_KEY = "lgk_test_mock_key"


@pytest.fixture
def client() -> LogionClient:
    """Provide a LogionClient pointed at the local Prism mock server."""
    return LogionClient(
        api_key=MOCK_API_KEY,
        base_url=MOCK_BASE_URL,
        max_retries=0,
    )

"""Tests for LogionClient initialization and configuration."""

from __future__ import annotations

from logion import LogionClient


def test_client_default_config() -> None:
    """Client uses default base URL when none provided."""
    client = LogionClient(api_key="lgk_test")
    assert client._http._client.base_url == ("https://api.logion.dev")
    client.close()


def test_client_custom_base_url() -> None:
    """Client uses custom base URL when provided."""
    client = LogionClient(
        api_key="lgk_test",
        base_url="http://localhost:4010",
    )
    assert client._http._client.base_url == "http://localhost:4010"
    client.close()


def test_client_context_manager() -> None:
    """Client works as a context manager."""
    with LogionClient(api_key="lgk_test") as client:
        assert client is not None


def test_client_no_api_key() -> None:
    """Client can be created without an API key (health-endpoint only)."""
    client = LogionClient()
    assert client._http._config.api_key == ""
    client.close()


def test_client_v1_namespace_exists() -> None:
    """Client exposes a v1 namespace."""
    client = LogionClient(api_key="lgk_test")
    assert hasattr(client, "v1")
    assert client.v1 is not None
    client.close()

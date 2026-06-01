# SPDX-License-Identifier: MIT
"""Tests for LogionClient initialization and configuration."""

from __future__ import annotations

import httpx

from logion import LogionClient
from logion.v1 import V1Namespace


def test_client_default_config(monkeypatch) -> None:
    """Client uses default base URL when none provided."""
    monkeypatch.delenv("LOGION_API_KEY", raising=False)
    monkeypatch.delenv("LOGION_BASE_URL", raising=False)
    client = LogionClient(api_key="lgk_test")
    assert client._http._client.base_url == httpx.URL("https://api.logion.dev")
    client.close()


def test_client_custom_base_url() -> None:
    """Client uses custom base URL when provided."""
    client = LogionClient(
        api_key="lgk_test",
        base_url="http://localhost:4010",
    )
    assert client._http._client.base_url == httpx.URL("http://localhost:4010")
    client.close()


def test_client_context_manager() -> None:
    """Client works as a context manager."""
    with LogionClient(api_key="lgk_test") as client:
        assert client is not None


def test_client_no_api_key(monkeypatch) -> None:
    """Client can be created without an API key
    (health-endpoint only)."""
    monkeypatch.delenv("LOGION_API_KEY", raising=False)
    monkeypatch.delenv("LOGION_BASE_URL", raising=False)
    client = LogionClient()
    assert client._http._config.api_key == ""
    client.close()


def test_client_v1_namespace_exists() -> None:
    """Client exposes a v1 namespace."""
    client = LogionClient(api_key="lgk_test")
    assert hasattr(client, "v1")
    assert client.v1 is not None
    client.close()


def test_client_reads_env_api_key(monkeypatch) -> None:
    """LogionClient() reads LOGION_API_KEY from env when
    no arg given."""
    monkeypatch.setenv("LOGION_API_KEY", "lgk_from_env")
    monkeypatch.delenv("LOGION_BASE_URL", raising=False)
    client = LogionClient()
    assert client._http._config.api_key == "lgk_from_env"
    client.close()


def test_client_reads_env_base_url(monkeypatch) -> None:
    """LogionClient() reads LOGION_BASE_URL from env when
    no arg given."""
    monkeypatch.delenv("LOGION_API_KEY", raising=False)
    monkeypatch.setenv("LOGION_BASE_URL", "http://env-host")
    client = LogionClient()
    assert client._http._config.base_url == "http://env-host"
    client.close()


def test_explicit_args_override_env(monkeypatch) -> None:
    """Explicit args override env vars."""
    monkeypatch.setenv("LOGION_API_KEY", "env_key")
    monkeypatch.setenv("LOGION_BASE_URL", "http://env-host")
    client = LogionClient(
        api_key="explicit_key",
        base_url="http://explicit-host",
    )
    assert client._http._config.api_key == "explicit_key"
    assert client._http._config.base_url == "http://explicit-host"
    client.close()


def test_v1_property_returns_v1_namespace() -> None:
    """v1 property returns V1Namespace instance."""
    client = LogionClient(api_key="lgk_test")
    assert isinstance(client.v1, V1Namespace)
    client.close()

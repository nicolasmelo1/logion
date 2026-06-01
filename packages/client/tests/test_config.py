# SPDX-License-Identifier: MIT
"""Tests for logion._config module."""

from __future__ import annotations

from logion._config import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    ClientConfig,
    resolve_config,
    resolve_env_or,
)


class TestResolveEnvOr:
    """Tests for resolve_env_or helper."""

    def test_returns_default_when_env_not_set(self, monkeypatch) -> None:
        """resolve_env_or returns default when env var not set."""
        monkeypatch.delenv("LOGION_TEST_VAR", raising=False)
        result = resolve_env_or("LOGION_TEST_VAR", "fallback")
        assert result == "fallback"

    def test_returns_env_value_when_set(self, monkeypatch) -> None:
        """resolve_env_or returns env var value when set."""
        monkeypatch.setenv("LOGION_TEST_VAR", "from_env")
        result = resolve_env_or("LOGION_TEST_VAR", "fallback")
        assert result == "from_env"


class TestResolveConfig:
    """Tests for resolve_config function."""

    def test_explicit_values_take_precedence(self, monkeypatch) -> None:
        """Explicit values override env vars."""
        monkeypatch.setenv("LOGION_API_KEY", "env_key")
        monkeypatch.setenv("LOGION_BASE_URL", "http://env-url")

        config = resolve_config(
            api_key="explicit_key",
            base_url="http://explicit-url",
        )
        assert config.api_key == "explicit_key"
        assert config.base_url == "http://explicit-url"

    def test_falls_back_to_env_vars(self, monkeypatch) -> None:
        """None values fall back to env vars."""
        monkeypatch.setenv("LOGION_API_KEY", "env_key")
        monkeypatch.setenv("LOGION_BASE_URL", "http://env-url")

        config = resolve_config(
            api_key=None,
            base_url=None,
        )
        assert config.api_key == "env_key"
        assert config.base_url == "http://env-url"

    def test_falls_back_to_defaults(self, monkeypatch) -> None:
        """None values with no env vars fall back to defaults."""
        monkeypatch.delenv("LOGION_API_KEY", raising=False)
        monkeypatch.delenv("LOGION_BASE_URL", raising=False)

        config = resolve_config()
        assert config.api_key == ""
        assert config.base_url == DEFAULT_BASE_URL
        assert config.timeout == DEFAULT_TIMEOUT
        assert config.max_retries == DEFAULT_MAX_RETRIES
        assert config.extra_headers == {}

    def test_explicit_none_uses_defaults(self, monkeypatch) -> None:
        """Explicit None uses defaults when no env vars set."""
        monkeypatch.delenv("LOGION_API_KEY", raising=False)
        monkeypatch.delenv("LOGION_BASE_URL", raising=False)

        config = resolve_config(
            api_key=None,
            base_url=None,
            timeout=None,
            max_retries=None,
            extra_headers=None,
        )
        assert config.base_url == DEFAULT_BASE_URL
        assert config.api_key == ""
        assert config.timeout == DEFAULT_TIMEOUT
        assert config.max_retries == DEFAULT_MAX_RETRIES
        assert config.extra_headers == {}


class TestClientConfig:
    """Tests for ClientConfig dataclass."""

    def test_stores_values_correctly(self) -> None:
        """ClientConfig stores values correctly."""
        config = ClientConfig(
            base_url="http://example.com",
            api_key="lgk_test",
            timeout=10.0,
            max_retries=5,
            extra_headers={"X-Custom": "val"},
        )
        assert config.base_url == "http://example.com"
        assert config.api_key == "lgk_test"
        assert config.timeout == 10.0
        assert config.max_retries == 5
        assert config.extra_headers == {"X-Custom": "val"}

    def test_default_values(self) -> None:
        """ClientConfig uses defaults when no args given."""
        config = ClientConfig()
        assert config.base_url == DEFAULT_BASE_URL
        assert config.api_key == ""
        assert config.timeout == DEFAULT_TIMEOUT
        assert config.max_retries == DEFAULT_MAX_RETRIES
        assert config.extra_headers == {}

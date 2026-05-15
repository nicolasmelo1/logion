"""Tests for CLI config resolution."""

from __future__ import annotations

import argparse

import pytest

from cli._config import (
    DEFAULT_BASE_URL,
    is_admin_enabled,
    is_truthy,
    resolve_config_from_args,
)


def test_default_base_url() -> None:
    assert DEFAULT_BASE_URL == "https://api.logion.dev"


def test_is_truthy() -> None:
    assert is_truthy("1") is True
    assert is_truthy("true") is True
    assert is_truthy("yes") is True
    assert is_truthy("on") is True
    assert is_truthy("0") is False
    assert is_truthy("false") is False
    assert is_truthy(None) is False


def test_is_admin_enabled_defaults_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOGION_ENABLE_ADMIN", raising=False)
    assert is_admin_enabled() is False


def test_is_admin_enabled_truthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    assert is_admin_enabled() is True


def test_resolve_from_args_defaults() -> None:
    args = argparse.Namespace(
        api_key=None,
        base_url=None,
        json_output=False,
        timeout=None,
        max_retries=None,
    )
    config = resolve_config_from_args(args)
    assert config.api_key is None
    assert config.base_url == DEFAULT_BASE_URL
    assert config.json_output is False


def test_resolve_from_args_explicit() -> None:
    args = argparse.Namespace(
        api_key="lgk_test",
        base_url="http://localhost:4010",
        json_output=True,
        timeout=10.0,
        max_retries=1,
    )
    config = resolve_config_from_args(args)
    assert config.api_key == "lgk_test"
    assert config.base_url == "http://localhost:4010"
    assert config.json_output is True
    assert config.timeout == 10.0
    assert config.max_retries == 1


def test_resolve_env_vars_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGION_API_KEY", "lgk_env")
    monkeypatch.setenv("LOGION_BASE_URL", "http://env:4010")
    args = argparse.Namespace(
        api_key=None,
        base_url=None,
        json_output=False,
        timeout=None,
        max_retries=None,
    )
    config = resolve_config_from_args(args)
    assert config.api_key == "lgk_env"
    assert config.base_url == "http://env:4010"


def test_args_override_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGION_API_KEY", "lgk_env")
    monkeypatch.setenv("LOGION_BASE_URL", "http://env:4010")
    args = argparse.Namespace(
        api_key="lgk_explicit",
        base_url="http://explicit:4010",
        json_output=False,
        timeout=None,
        max_retries=None,
    )
    config = resolve_config_from_args(args)
    assert config.api_key == "lgk_explicit"
    assert config.base_url == "http://explicit:4010"

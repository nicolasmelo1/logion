"""Tests for the health command."""

from __future__ import annotations

from typing import Any

import pytest

from cli.main import main


class FakeHealthResource:
    """Fake health resource returning canned data."""

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self._response = response or {"status": "ok"}

    def check(self) -> dict[str, Any]:
        return self._response


class FakeV1Namespace:
    """Fake v1 namespace with configurable health resource."""

    def __init__(self, health: FakeHealthResource | None = None) -> None:
        self.health = health or FakeHealthResource()


class FakeClient:
    """Fake LogionClient for unit tests."""

    def __init__(self, *, v1: FakeV1Namespace | None = None) -> None:
        self.v1 = v1 or FakeV1Namespace()

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    """Replace make_client to return *fake*."""
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_health_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """health --json prints valid JSON with status."""
    fake = FakeClient(v1=FakeV1Namespace(health=FakeHealthResource()))
    _patch_client(monkeypatch, fake)
    assert main(["health", "--json"]) == 0


def test_health_human_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """health without --json prints the dict repr."""
    fake = FakeClient(v1=FakeV1Namespace(health=FakeHealthResource()))
    _patch_client(monkeypatch, fake)
    assert main(["health"]) == 0

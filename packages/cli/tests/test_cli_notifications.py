"""Tests for the notifications commands."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cli.main import main


class FakeNotificationsResource:
    """Fake notifications resource."""

    def __init__(
        self,
        unread_count: int = 0,
        items: list[dict[str, Any]] | None = None,
    ) -> None:
        self._unread_count = unread_count
        self._items = items or []
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

    def get_unread_count(self) -> int:
        self.last_call = ("get_unread_count", {})
        return self._unread_count

    def list(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.last_call = ("list", kwargs)
        return self._items


class FakeV1Namespace:
    def __init__(self, notifications: FakeNotificationsResource) -> None:
        self.notifications = notifications


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_notifications_peek_no_unread(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """notifications peek with 0 unread prints 'No unread' message."""
    notifications = FakeNotificationsResource(unread_count=0)
    fake = FakeClient(v1=FakeV1Namespace(notifications=notifications))
    _patch_client(monkeypatch, fake)
    code = main(["notifications", "peek"])
    assert code == 0
    output = capsys.readouterr().out
    assert "No unread" in output


def test_notifications_peek_with_unread(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """notifications peek with unread items lists them."""
    items = [
        {"id": "n1", "type": "course_update", "message": "Course updated"},
        {"id": "n2", "type": "new_review", "message": "New review"},
    ]
    notifications = FakeNotificationsResource(unread_count=3, items=items)
    fake = FakeClient(v1=FakeV1Namespace(notifications=notifications))
    _patch_client(monkeypatch, fake)
    code = main(["notifications", "peek", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.notifications.peek"
    assert payload["data"]["unread_count"] == 3
    assert len(payload["data"]["items"]) == 2


def test_notifications_peek_no_unread_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """notifications peek --json with 0 unread returns empty items."""
    notifications = FakeNotificationsResource(unread_count=0)
    fake = FakeClient(v1=FakeV1Namespace(notifications=notifications))
    _patch_client(monkeypatch, fake)
    code = main(["notifications", "peek", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.notifications.peek"
    assert payload["data"]["unread_count"] == 0
    assert payload["data"]["items"] == []

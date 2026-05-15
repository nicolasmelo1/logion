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
        unread_count: Any = None,
        list_response: Any = None,
    ) -> None:
        self._unread_count = unread_count
        self._list_response = list_response
        self.last_list_call: dict[str, Any] = {}

    def get_unread_count(self) -> Any:
        if self._unread_count is not None:
            return self._unread_count
        return {"unread_count": 5}

    def list(self, **kwargs: Any) -> Any:
        self.last_list_call = kwargs
        if self._list_response is not None:
            return self._list_response
        return {"items": [], "next_cursor": None}


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


def test_unread_count_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """notifications unread-count --json emits count."""
    notif = FakeNotificationsResource()
    fake = FakeClient(v1=FakeV1Namespace(notifications=notif))
    _patch_client(monkeypatch, fake)
    assert main(["notifications", "unread-count", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["unread_count"] == 5


def test_unread_count_human(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """notifications unread-count without --json."""
    notif = FakeNotificationsResource()
    fake = FakeClient(v1=FakeV1Namespace(notifications=notif))
    _patch_client(monkeypatch, fake)
    assert main(["notifications", "unread-count"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["unread_count"] == 5


def test_notifications_list_basic(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """notifications list forwards params to SDK."""
    notif = FakeNotificationsResource()
    fake = FakeClient(v1=FakeV1Namespace(notifications=notif))
    _patch_client(monkeypatch, fake)
    assert main(["notifications", "list", "--unread-only"]) == 0
    assert notif.last_list_call["unread_only"] is True
    data = json.loads(capsys.readouterr().out)
    assert "items" in data


def test_notifications_list_with_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """notifications list forwards all filters."""
    notif = FakeNotificationsResource()
    fake = FakeClient(v1=FakeV1Namespace(notifications=notif))
    _patch_client(monkeypatch, fake)
    assert (
        main([
            "notifications",
            "list",
            "--limit",
            "20",
            "--cursor",
            "abc",
            "--notification-type",
            "course_update",
        ])
        == 0
    )
    assert notif.last_list_call["limit"] == 20
    assert notif.last_list_call["cursor"] == "abc"
    assert notif.last_list_call["notification_type"] == "course_update"
    data = json.loads(capsys.readouterr().out)
    assert "items" in data

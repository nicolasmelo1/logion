# SPDX-License-Identifier: MIT
"""Tests for the notifications commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from cli.main import main


@dataclass
class CountModel:
    unread_count: int


class FakeNotificationsResource:
    """Fake notifications resource."""

    def __init__(
        self,
        unread_count: object = 0,
        items: list[dict[str, Any]] | None = None,
    ) -> None:
        self._unread_count = unread_count
        self._items = items or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_unread_count(self) -> object:
        self.calls.append(("get_unread_count", {}))
        return self._unread_count

    def list(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list", kwargs))
        return {"items": self._items, "next_cursor": None}


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


def test_notifications_unread_count_v1_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    notifications = FakeNotificationsResource(unread_count={"unread_count": 7})
    fake = FakeClient(v1=FakeV1Namespace(notifications=notifications))
    _patch_client(monkeypatch, fake)

    code = main(["notifications", "unread-count", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "version": "v1",
        "kind": "logion.notifications.unread-count",
        "data": {"unread_count": 7},
    }


def test_notifications_list_v1_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    items = [{"id": "n1", "title": "Course updated"}]
    notifications = FakeNotificationsResource(unread_count=1, items=items)
    fake = FakeClient(v1=FakeV1Namespace(notifications=notifications))
    _patch_client(monkeypatch, fake)

    code = main([
        "notifications",
        "list",
        "--unread-only",
        "--limit",
        "5",
        "--json",
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.notifications.list"
    assert payload["data"] == {"items": items, "next_cursor": None}
    assert notifications.calls[-1] == (
        "list",
        {
            "unread_only": True,
            "notification_type": None,
            "limit": 5,
            "cursor": None,
        },
    )


def test_peek_when_count_zero_does_not_call_list(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    notifications = FakeNotificationsResource(
        unread_count=CountModel(unread_count=0)
    )
    fake = FakeClient(v1=FakeV1Namespace(notifications=notifications))
    _patch_client(monkeypatch, fake)

    code = main(["notifications", "peek", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "version": "v1",
        "kind": "logion.notifications.peek",
        "data": {"unread_count": 0, "items": []},
    }
    assert notifications.calls == [("get_unread_count", {})]


def test_peek_when_count_positive_calls_list_with_limit_five(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    items = [
        {"id": "n1", "title": "Course updated"},
        {"id": "n2", "title": "New review"},
    ]
    notifications = FakeNotificationsResource(
        unread_count={"unread_count": 3},
        items=items,
    )
    fake = FakeClient(v1=FakeV1Namespace(notifications=notifications))
    _patch_client(monkeypatch, fake)

    code = main(["notifications", "peek", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.notifications.peek"
    assert payload["data"] == {"unread_count": 3, "items": items}
    assert notifications.calls == [
        ("get_unread_count", {}),
        ("list", {"unread_only": True, "limit": 5}),
    ]


def test_peek_v1_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    notifications = FakeNotificationsResource(unread_count=1, items=[])
    fake = FakeClient(v1=FakeV1Namespace(notifications=notifications))
    _patch_client(monkeypatch, fake)

    code = main(["notifications", "peek", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.notifications.peek"
    assert set(payload["data"].keys()) == {"unread_count", "items"}

"""Tests for the reports commands."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cli.main import main


class FakeReportsResource:
    """Fake reports resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create", kwargs)
        return {
            "id": "770e8400-e29b-41d4-a716-446655440002",
            "target_type": kwargs["target_type"],
            "target_id": kwargs["target_id"],
            "reason": kwargs["reason"],
        }


class FakeV1Namespace:
    def __init__(self, reports: FakeReportsResource) -> None:
        self.reports = reports


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_reports_create_calls_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """reports create --yes forwards args to SDK."""
    reports = FakeReportsResource()
    fake = FakeClient(v1=FakeV1Namespace(reports=reports))
    _patch_client(monkeypatch, fake)
    code = main([
        "reports",
        "create",
        "--target-type",
        "course",
        "--target-id",
        "550e8400-e29b-41d4-a716-446655440000",
        "--reason",
        "spam",
        "--description",
        "Suspicious listing",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = reports.last_call
    assert method == "create"
    assert kwargs["target_type"] == "course"
    assert kwargs["target_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["reason"] == "spam"
    assert kwargs["description"] == "Suspicious listing"
    data = json.loads(capsys.readouterr().out)
    assert data["target_type"] == "course"


def test_reports_create_without_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reports create works without --description."""
    reports = FakeReportsResource()
    fake = FakeClient(v1=FakeV1Namespace(reports=reports))
    _patch_client(monkeypatch, fake)
    code = main([
        "reports",
        "create",
        "--target-type",
        "agent",
        "--target-id",
        "990e8400-e29b-41d4-a716-446655440004",
        "--reason",
        "harassment",
        "--yes",
        "--json",
    ])
    assert code == 0
    _method, kwargs = reports.last_call
    assert "description" not in kwargs


def test_reports_create_without_yes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """reports create refuses without --yes."""
    code = main([
        "reports",
        "create",
        "--target-type",
        "course",
        "--target-id",
        "550e8400-e29b-41d4-a716-446655440000",
        "--reason",
        "spam",
    ])
    assert code == 2
    stderr = capsys.readouterr().err
    assert "Re-run with --yes to create this report." in stderr


def test_reports_create_invalid_target_type() -> None:
    """reports create rejects invalid target-type choices."""
    with pytest.raises(SystemExit):
        main([
            "reports",
            "create",
            "--target-type",
            "invalid",
            "--target-id",
            "550e8400-e29b-41d4-a716-446655440000",
            "--reason",
            "spam",
        ])


def test_reports_create_invalid_reason() -> None:
    """reports create rejects invalid reason choices."""
    with pytest.raises(SystemExit):
        main([
            "reports",
            "create",
            "--target-type",
            "course",
            "--target-id",
            "550e8400-e29b-41d4-a716-446655440000",
            "--reason",
            "invalid",
        ])


def test_reports_create_missing_required() -> None:
    """reports create fails without required args."""
    with pytest.raises(SystemExit):
        main(["reports", "create"])


def test_reports_create_empty_target_id() -> None:
    """reports create rejects empty --target-id."""
    code = main([
        "reports",
        "create",
        "--target-type",
        "course",
        "--target-id",
        "",
        "--reason",
        "spam",
        "--yes",
        "--json",
    ])
    assert code == 2


def test_reports_create_invalid_uuid() -> None:
    """reports create rejects an invalid UUID --target-id."""
    code = main([
        "reports",
        "create",
        "--target-type",
        "course",
        "--target-id",
        "not-a-uuid",
        "--reason",
        "spam",
        "--yes",
        "--json",
    ])
    assert code == 2

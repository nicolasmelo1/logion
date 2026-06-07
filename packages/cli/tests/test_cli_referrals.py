# SPDX-License-Identifier: MIT
"""Tests for referrals CLI commands."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cli.main import main


class FakeReferralsResource:
    """Fake referrals resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

    def get_code(self) -> dict[str, Any]:
        self.last_call = ("get_code", {})
        return {"referral_code": "ABC123"}

    def get_link(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_link", kwargs)
        return {
            "course_id": kwargs["course_id"],
            "referral_link": "https://logion.app/r/ABC123/c/"
            + kwargs["course_id"],
        }

    def get_stats(self) -> dict[str, Any]:
        self.last_call = ("get_stats", {})
        return {
            "total_referrals": 5,
            "product_lane": 3,
            "creator_lane": 2,
        }

    def list_attributions(self) -> list[dict[str, Any]]:
        self.last_call = ("list_attributions", {})
        return [
            {
                "id": "attr-1",
                "referred_user_id": "u-001",
                "lane": "product",
                "attributed_at": "2026-06-01T00:00:00Z",
            }
        ]


class FakeV1Namespace:
    def __init__(self, referrals_resource: FakeReferralsResource) -> None:
        self.referrals = referrals_resource


class FakeClient:
    def __init__(self, referrals_resource: FakeReferralsResource) -> None:
        self.v1 = FakeV1Namespace(referrals_resource)
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    referrals_resource: FakeReferralsResource,
) -> FakeClient:
    fake = FakeClient(referrals_resource)
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)
    return fake


def test_referrals_code_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """referrals code emits the v1 JSON envelope."""
    referrals_resource = FakeReferralsResource()
    _patch_client(monkeypatch, referrals_resource)

    assert main(["referrals", "code", "--json"]) == 0

    assert referrals_resource.last_call == ("get_code", {})
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.referrals.code"
    assert payload["data"]["referral_code"] == "ABC123"


def test_referrals_link_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """referrals link refuses to share without --yes."""
    referrals_resource = FakeReferralsResource()
    _patch_client(monkeypatch, referrals_resource)

    course_id = "11111111-1111-1111-1111-111111111111"
    assert main(["referrals", "link", course_id]) == 2

    assert referrals_resource.last_call == ("", {})
    assert "--yes" in capsys.readouterr().err


def test_referrals_link_rejects_invalid_uuid(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """referrals link rejects a non-UUID course_id with exit code 2."""
    referrals_resource = FakeReferralsResource()
    _patch_client(monkeypatch, referrals_resource)

    assert main(["referrals", "link", "not-a-uuid", "--yes"]) == 2

    assert referrals_resource.last_call == ("", {})
    assert "UUID" in capsys.readouterr().err


def test_referrals_link_json_with_yes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """referrals link --yes forwards course_id and renders link."""
    referrals_resource = FakeReferralsResource()
    _patch_client(monkeypatch, referrals_resource)

    course_id = "11111111-1111-1111-1111-111111111111"
    assert main(["referrals", "link", course_id, "--yes", "--json"]) == 0

    assert referrals_resource.last_call == (
        "get_link",
        {"course_id": course_id},
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.referrals.link"
    assert payload["data"]["referral_link"].startswith("https://logion.app/r/")


def test_referrals_stats_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """referrals stats emits the v1 JSON envelope."""
    referrals_resource = FakeReferralsResource()
    _patch_client(monkeypatch, referrals_resource)

    assert main(["referrals", "stats", "--json"]) == 0

    assert referrals_resource.last_call == ("get_stats", {})
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.referrals.stats"
    assert payload["data"]["total_referrals"] == 5


def test_referrals_attributions_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """referrals attributions emits the v1 JSON envelope."""
    referrals_resource = FakeReferralsResource()
    _patch_client(monkeypatch, referrals_resource)

    assert main(["referrals", "attributions", "--json"]) == 0

    assert referrals_resource.last_call == (
        "list_attributions",
        {},
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.referrals.attributions"
    assert payload["data"][0]["id"] == "attr-1"

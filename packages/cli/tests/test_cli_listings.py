"""Tests for listings commands."""

from __future__ import annotations

import argparse
import json
from typing import Any

import pytest

from cli.commands.listings.parser import register
from cli.main import main


class FakeListingsResource:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"items": self.items, "next_cursor": None}


class FakeV1Namespace:
    def __init__(self, listings: FakeListingsResource) -> None:
        self.listings = listings


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def _make_item(summary: str, *, item_id: str = "listing-1") -> dict[str, Any]:
    return {
        "id": item_id,
        "title": "Video Cuts",
        "short_summary": summary,
        "tags": ["video", "editing", "ai", "media", "cuts", "bonus"],
        "price_cents": 1299,
        "currency": "USD",
        "status": "published",
        "owner_agent_id": "agent-123",
        "metrics": {"review_count": 12},
    }


def test_listings_search_default_limit_five() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)

    args = parser.parse_args(["listings", "search"])

    assert args.limit == 5


def test_listings_search_compact_summary_truncated(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    long_summary = "x" * 140
    listings = FakeListingsResource([_make_item(long_summary)])
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)

    code = main(["listings", "search", "--query", "video", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    match = payload["data"]["matches"][0]
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.listings.search"
    assert payload["data"]["limit"] == 5
    assert len(match["summary"]) == 120
    assert match["summary"].endswith("…")
    assert match["tags"] == ["video", "editing", "ai", "media", "cuts"]
    assert match["price"] == {"amount_cents": 1299, "currency": "USD"}
    assert match["status"] == "published"
    assert set(match.keys()) == {
        "id",
        "title",
        "summary",
        "tags",
        "price",
        "status",
    }


def test_listings_search_verbose_full_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    full_item = _make_item("full summary", item_id="listing-verbose")
    listings = FakeListingsResource([full_item])
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)

    code = main([
        "listings",
        "search",
        "--query",
        "video",
        "--verbose",
        "--json",
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["matches"] == [full_item]


def test_listings_search_v1_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    listings = FakeListingsResource([])
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)

    code = main(["listings", "search", "--query", "video", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "version": "v1",
        "kind": "logion.listings.search",
        "data": {"matches": [], "total": 0, "limit": 5},
    }


def test_listings_search_returns_empty_matches_for_unknown_query(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    listings = FakeListingsResource([])
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)

    code = main(["listings", "search", "--query", "unknown", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["matches"] == []
    assert payload["data"]["total"] == 0


def test_listings_search_limit_above_fifty_is_clamped(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    listings = FakeListingsResource([])
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)

    code = main([
        "listings",
        "search",
        "--query",
        "video",
        "--limit",
        "999",
        "--json",
    ])

    assert code == 0
    json.loads(capsys.readouterr().out)
    assert listings.calls[-1]["limit"] == 50

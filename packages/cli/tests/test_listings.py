"""Tests for the listings search command."""

from __future__ import annotations

from typing import Any

import pytest

from cli.main import main


class FakeListingsResource:
    """Fake listings resource."""

    def __init__(self, response: Any = None) -> None:
        self._response = response
        self.last_call: dict[str, Any] = {}

    def search(self, **kwargs: Any) -> Any:
        self.last_call = kwargs
        if self._response is not None:
            return self._response
        return {"items": [], "next_cursor": None}


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


def test_listings_search_basic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """listings search --query rag emits results."""
    listings = FakeListingsResource()
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)
    assert main(["listings", "search", "--query", "rag"]) == 0
    assert listings.last_call["query"] == "rag"


def test_listings_search_with_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """listings search forwards all filters to the SDK."""
    listings = FakeListingsResource()
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)
    assert (
        main([
            "listings",
            "search",
            "--query",
            "rag",
            "--language",
            "pt",
            "--limit",
            "10",
            "--sort",
            "newest",
        ])
        == 0
    )
    assert listings.last_call["query"] == "rag"
    assert listings.last_call["language"] == "pt"
    assert listings.last_call["limit"] == 10
    assert listings.last_call["sort"] == "newest"


def test_listings_search_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """listings search --json outputs valid JSON."""
    listings = FakeListingsResource(response={"items": []})
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)
    assert main(["listings", "search", "--json"]) == 0

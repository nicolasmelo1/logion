# SPDX-License-Identifier: MIT
"""Tests for the indexed listings command."""

from __future__ import annotations

import argparse
import json
from typing import Any

import pytest

from cli.commands.indexed.parser import register
from cli.main import main


class FakeIndexedListingsResource:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def get(self, *, listing_id: str) -> dict[str, Any]:
        self.calls.append({"listing_id": listing_id})
        return self.payload


class FakeV1Namespace:
    def __init__(self, indexed_listings: FakeIndexedListingsResource) -> None:
        self.indexed_listings = indexed_listings


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_indexed_get_forwards_listing_id_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {
        "id": "idx-1",
        "title": "Indexed Course",
        "original_author": "alice",
        "source_url": "https://example.com/course",
        "source_hub": "github",
        "tier": "indexed",
        "license_spdx": "MIT",
        "observation_status": "observed",
        "summary": "A short summary.",
    }
    resource = FakeIndexedListingsResource(payload)
    fake = FakeClient(v1=FakeV1Namespace(indexed_listings=resource))
    _patch_client(monkeypatch, fake)

    code = main(["indexed", "get", "idx-1", "--json"])

    assert code == 0
    assert resource.calls == [{"listing_id": "idx-1"}]
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["kind"] == "logion.indexed.get"
    assert emitted["data"]["id"] == "idx-1"


def test_indexed_get_human_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {
        "id": "idx-2",
        "title": "Indexed Course Two",
        "original_author": "bob",
        "source_url": "https://example.com/course2",
        "source_hub": "github",
        "tier": "improving",
        "license_spdx": "Apache-2.0",
        "observation_status": "observed",
        "summary": "Another summary.",
    }
    resource = FakeIndexedListingsResource(payload)
    fake = FakeClient(v1=FakeV1Namespace(indexed_listings=resource))
    _patch_client(monkeypatch, fake)

    code = main(["indexed", "get", "idx-2"])

    assert code == 0
    output = capsys.readouterr().out
    assert "ID: idx-2" in output
    assert "Title: Indexed Course Two" in output
    assert "Another summary." in output


def test_indexed_get_parses_listing_id() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)

    args = parser.parse_args(["indexed", "get", "idx-3"])
    assert args.listing_id == "idx-3"

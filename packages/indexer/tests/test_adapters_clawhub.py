"""Tests for the ClawHub public skills feed adapter."""

from __future__ import annotations

import json

import pytest

from logion_indexer.adapters.clawhub import ClawhubAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

BASE = "https://clawhub.ai"
ROBOTS = f"{BASE}/robots.txt"
FEED = f"{BASE}/v1/feeds/skills"


def _transport() -> FakeTransport:
    transport = FakeTransport()
    transport.set_response(ROBOTS, HttpResponse(200, b""))
    return transport


def _feed(entries: list[dict]) -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps({"schemaVersion": 1, "entries": entries}).encode(),
    )


def _entry(
    *,
    title: str = "Deploy",
    state: str = "available",
    repo: str = "acme/skills",
    path: str = "skills/deploy",
) -> dict:
    return {
        "type": "skill",
        "id": "@acme/deploy",
        "title": title,
        "description": "Deploy safely",
        "state": state,
        "install": {
            "candidates": [
                {
                    "sourceRef": "public-github",
                    "version": "abc123",
                    "integrity": "sha256:integrity",
                    "github": {
                        "repo": repo,
                        "path": path,
                        "commit": "abc123",
                        "contentHash": "content-hash",
                    },
                }
            ],
        },
    }


class TestClawhubAdapter:
    def test_reads_verified_github_candidates(self) -> None:
        transport = _transport()
        transport.set_response(FEED, _feed([_entry()]))

        results = list(ClawhubAdapter(transport).discover(f"{BASE}/"))

        assert len(results) == 1
        skill = results[0]
        assert str(skill.canonical) == "gh:acme/skills#skills/deploy"
        assert skill.source_commit == "abc123"
        assert skill.summary == "Deploy safely"
        assert skill.channels[0].hub_verified is True
        assert dict(skill.channels[0].metadata) == {
            "version": "abc123",
            "integrity": "sha256:integrity",
            "contentHash": "content-hash",
        }

    def test_skips_hosted_unavailable_and_duplicate_entries(self) -> None:
        hosted = {
            "state": "available",
            "install": {"candidates": [{"sourceRef": "public-clawhub"}]},
        }
        transport = _transport()
        transport.set_response(
            FEED,
            _feed([
                hosted,
                _entry(state="unavailable"),
                _entry(),
                _entry(title="Duplicate"),
            ]),
        )

        results = list(ClawhubAdapter(transport).discover(BASE))

        assert len(results) == 1
        assert results[0].title == "Deploy"

    def test_limit_stops_immediately(self) -> None:
        transport = _transport()
        transport.set_response(
            FEED,
            _feed([
                _entry(),
                _entry(repo="other/skills", path="skills/other"),
            ]),
        )

        results = list(ClawhubAdapter(transport).discover(BASE, limit=1))

        assert len(results) == 1

    def test_invalid_json_is_reported(self) -> None:
        transport = _transport()
        transport.set_response(FEED, HttpResponse(200, b"not-json"))

        with pytest.raises(RuntimeError, match="invalid JSON"):
            list(ClawhubAdapter(transport).discover(BASE))

    def test_robots_disallow_is_reported(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            ROBOTS,
            HttpResponse(200, b"User-agent: *\nDisallow: /v1/\n"),
        )

        with pytest.raises(PermissionError, match=r"blocked by robots\.txt"):
            list(ClawhubAdapter(transport).discover(BASE))

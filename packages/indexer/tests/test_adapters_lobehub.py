"""Tests for the paginated LobeHub RSC adapter."""

from __future__ import annotations

import json

import pytest

from logion_indexer.adapters.lobehub import LobehubAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

BASE = "https://lobehub.com/skills"
ROBOTS = "https://lobehub.com/robots.txt"
PAGE_1 = f"{BASE}?page=1"
PAGE_2 = f"{BASE}?page=2"


def _item(
    identifier: str,
    repo_url: str,
    homepage: str,
    *,
    name: str = "Skill",
) -> dict:
    return {
        "identifier": identifier,
        "name": name,
        "description": "Description",
        "github": {"url": repo_url},
        "homepage": homepage,
        "license": "MIT",
    }


def _page(
    page: int,
    items: list[dict],
    *,
    page_size: int,
    total: int,
) -> HttpResponse:
    payload = (
        '77:["$",{"data":'
        + json.dumps(items, separators=(",", ":"))
        + "}]\n"
        + json.dumps(
            {
                "currentPage": page,
                "pageSize": page_size,
                "tab": "skills",
                "total": total,
            },
            separators=(",", ":"),
        )
    )
    return HttpResponse(200, payload.encode())


def _transport() -> FakeTransport:
    transport = FakeTransport()
    transport.set_response(ROBOTS, HttpResponse(200, b""))
    return transport


class TestLobehubAdapter:
    def test_paginates_and_emits_each_repository_once(self) -> None:
        acme = _item(
            "acme-skills-deploy",
            "https://github.com/acme/skills",
            "https://github.com/acme/skills/tree/main/skills/deploy",
            name="Deploy",
        )
        transport = _transport()
        transport.set_response(
            PAGE_1,
            _page(1, [acme, dict(acme)], page_size=2, total=4),
        )
        transport.set_response(
            PAGE_2,
            _page(
                2,
                [
                    acme,
                    _item(
                        "other-tools-review",
                        "https://github.com/other/tools",
                        "https://github.com/other/tools/tree/main/review",
                    ),
                ],
                page_size=2,
                total=4,
            ),
        )

        results = list(LobehubAdapter(transport).discover(BASE))

        assert [str(item.canonical) for item in results] == [
            "gh:acme/skills",
            "gh:other/tools",
        ]
        assert f"GET {PAGE_2}" in transport.call_log

    def test_limit_stops_before_next_page(self) -> None:
        item = _item(
            "acme-skills-deploy",
            "https://github.com/acme/skills",
            "https://github.com/acme/skills/tree/main/skills/deploy",
        )
        transport = _transport()
        transport.set_response(
            PAGE_1,
            _page(1, [item, dict(item)], page_size=2, total=4),
        )

        results = list(LobehubAdapter(transport).discover(BASE, limit=1))

        assert len(results) == 1
        assert f"GET {PAGE_2}" not in transport.call_log

    def test_missing_pagination_metadata_is_reported(self) -> None:
        transport = _transport()
        transport.set_response(PAGE_1, HttpResponse(200, b"invalid-rsc"))

        with pytest.raises(RuntimeError, match="pagination metadata"):
            list(LobehubAdapter(transport).discover(BASE))

    def test_robots_disallow_is_reported(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            ROBOTS,
            HttpResponse(200, b"User-agent: *\nDisallow: /skills\n"),
        )

        with pytest.raises(PermissionError, match=r"blocked by robots\.txt"):
            list(LobehubAdapter(transport).discover(BASE))

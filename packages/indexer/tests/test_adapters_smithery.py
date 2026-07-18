"""Tests for the Smithery public skills sitemap adapter."""

from __future__ import annotations

from unittest.mock import Mock

from logion_indexer.adapters.smithery import SmitheryAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

BASE = "https://smithery.ai"
ROBOTS = BASE + "/robots.txt"
INDEX = BASE + "/sitemap_index.xml"
SHARD_0 = BASE + "/skills/sitemap/0.xml"
SHARD_1 = BASE + "/skills/sitemap/1.xml"
SKILL_A = BASE + "/skills/maciek-telecki/resonance-lens"
SKILL_B = BASE + "/skills/openclaw/shopping-expert"


def _xml(root: str, urls: list[str]) -> bytes:
    body = "".join(f"<loc>{url}</loc>" for url in urls)
    return f"<{root}>{body}</{root}>".encode()


def _page(repository: str) -> bytes:
    return (
        '<span class="label">Repository</span><div>'
        f'<a href="https://github.com/{repository}">source</a></div>'
    ).encode()


def _transport() -> FakeTransport:
    transport = FakeTransport()
    transport.set_response(
        ROBOTS,
        HttpResponse(200, b"User-agent: *\nAllow: /"),
    )
    transport.set_response(
        INDEX,
        HttpResponse(
            200,
            _xml(
                "sitemapindex",
                [
                    SHARD_0,
                    SHARD_1,
                    BASE + "/servers/sitemap/0.xml",
                    "https://evil.example/skills/sitemap/0.xml",
                ],
            ),
        ),
    )
    duplicate_shard = _xml("urlset", [SKILL_A, SKILL_B])
    transport.set_response(SHARD_0, HttpResponse(200, duplicate_shard))
    transport.set_response(SHARD_1, HttpResponse(200, duplicate_shard))
    transport.set_response(SKILL_A, HttpResponse(200, _page("g4dz10r3k/lens")))
    transport.set_response(
        SKILL_B,
        HttpResponse(200, _page("openclaw/skills")),
    )
    return transport


def test_deduplicates_broken_shards_and_resolves_repository_label() -> None:
    transport = _transport()

    items = list(SmitheryAdapter(transport, Mock()).discover(BASE))

    assert [str(item.canonical) for item in items] == [
        "gh:g4dz10r3k/lens",
        "gh:openclaw/skills",
    ]
    skill_gets = [
        call
        for call in transport.call_log
        if call in {f"GET {SKILL_A}", f"GET {SKILL_B}"}
    ]
    assert len(skill_gets) == 2


def test_ignores_unrelated_github_links_without_repository_label() -> None:
    transport = _transport()
    transport.set_response(
        SKILL_A,
        HttpResponse(
            200, b'<a href="https://github.com/smithery-ai">footer</a>'
        ),
    )

    items = list(SmitheryAdapter(transport, Mock()).discover(BASE))

    assert [str(item.canonical) for item in items] == ["gh:openclaw/skills"]


def test_limit_avoids_fetching_later_skill_pages() -> None:
    transport = _transport()

    items = list(SmitheryAdapter(transport, Mock()).discover(BASE, limit=1))

    assert len(items) == 1
    page_gets = [
        call
        for call in transport.call_log
        if call in {f"GET {SKILL_A}", f"GET {SKILL_B}"}
    ]
    assert len(page_gets) == 1

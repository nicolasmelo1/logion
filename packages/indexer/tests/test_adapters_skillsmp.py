"""Tests for the SkillsMP public sitemap adapter."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from logion_indexer.adapters.skillsmp import SkillsMpAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

BASE = "https://skillsmp.com"
ROBOTS = BASE + "/robots.txt"
INDEX = BASE + "/sitemap.xml"
POPULAR = BASE + "/sitemaps/skills-popular.xml"
DISCOVERED = BASE + "/sitemaps/skills-discovered.xml"


def _xml(root: str, urls: list[str]) -> bytes:
    body = "".join(f"<loc>{url}</loc>" for url in urls)
    return f"<{root}>{body}</{root}>".encode()


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
                    POPULAR,
                    DISCOVERED,
                    BASE + "/sitemaps/pages.xml",
                    "https://evil.example/skills.xml",
                ],
            ),
        ),
    )
    transport.set_response(
        POPULAR,
        HttpResponse(
            200,
            _xml(
                "urlset",
                [
                    BASE + "/creators/anthropics/skills/skills-skill-creator",
                    BASE + "/creators/anthropics/skills/skills-pptx",
                    BASE + "/creators/openai/skills/docs",
                ],
            ),
        ),
    )
    transport.set_response(
        DISCOVERED,
        HttpResponse(
            200,
            _xml(
                "urlset",
                [
                    BASE + "/creators/openai/skills/docs",
                    BASE + "/not-a-skill",
                    "https://evil.example/creators/owner/repo/skill",
                ],
            ),
        ),
    )
    return transport


def test_discovers_unique_repositories_from_authorized_sitemaps() -> None:
    limiter = Mock()
    transport = _transport()

    items = list(SkillsMpAdapter(transport, limiter).discover(BASE))

    assert [str(item.canonical) for item in items] == [
        "gh:anthropics/skills",
        "gh:openai/skills",
    ]
    assert items[0].channels[0].hub_url.endswith("/skills-skill-creator")
    limiter.cap_rps.assert_called_once_with("skillsmp.com", 1.0)


def test_limit_stops_at_unique_repository_count() -> None:
    items = list(SkillsMpAdapter(_transport(), Mock()).discover(BASE, limit=1))

    assert len(items) == 1


def test_invalid_sitemap_is_explicit_failure() -> None:
    transport = _transport()
    transport.set_response(POPULAR, HttpResponse(200, b"not xml"))

    with pytest.raises(RuntimeError, match="invalid XML"):
        list(SkillsMpAdapter(transport, Mock()).discover(BASE))

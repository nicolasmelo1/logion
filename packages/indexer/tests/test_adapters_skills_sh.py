"""Tests for the skills.sh sitemap adapter."""

from __future__ import annotations

import pytest

from logion_indexer.adapters.skills_sh import SkillsShAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

BASE = "https://www.skills.sh"
ROBOTS = f"{BASE}/robots.txt"
INDEX = f"{BASE}/sitemap.xml"
SKILLS_1 = f"{BASE}/sitemap-skills-1.xml"
SKILLS_2 = f"{BASE}/sitemap-skills-2.xml"


def _sitemap(*urls: str, index: bool = False) -> HttpResponse:
    root = "sitemapindex" if index else "urlset"
    item = "sitemap" if index else "url"
    body = "".join(f"<{item}><loc>{url}</loc></{item}>" for url in urls)
    return HttpResponse(200, f"<{root}>{body}</{root}>".encode())


def _transport() -> FakeTransport:
    transport = FakeTransport()
    transport.set_response(ROBOTS, HttpResponse(200, b""))
    return transport


class TestSkillsShAdapter:
    def test_reads_skill_sitemaps_and_emits_each_repo_once(self) -> None:
        transport = _transport()
        transport.set_response(
            INDEX,
            _sitemap(
                f"{BASE}/sitemap-misc.xml",
                SKILLS_1,
                "https://evil.example/sitemap-skills-1.xml",
                SKILLS_2,
                index=True,
            ),
        )
        transport.set_response(
            SKILLS_1,
            _sitemap(
                f"{BASE}/octocat/skills/foo",
                f"{BASE}/octocat/skills/bar",
                "https://evil.example/acme/agents/injected",
            ),
        )
        transport.set_response(
            SKILLS_2,
            _sitemap(f"{BASE}/acme/agents/deploy"),
        )

        results = list(SkillsShAdapter(transport).discover(f"{BASE}/"))

        assert [str(item.canonical) for item in results] == [
            "gh:octocat/skills",
            "gh:acme/agents",
        ]
        assert all(
            item.channels[0].hub_slug == "skills_sh" for item in results
        )
        assert all(item.channels[0].hub_url == BASE for item in results)
        assert f"GET {SKILLS_1}" in transport.call_log
        assert f"GET {SKILLS_2}" in transport.call_log
        assert not any("evil.example" in call for call in transport.call_log)
        assert not any("sitemap-misc" in call for call in transport.call_log)

    def test_limit_stops_without_fetching_next_sitemap(self) -> None:
        transport = _transport()
        transport.set_response(
            INDEX,
            _sitemap(SKILLS_1, SKILLS_2, index=True),
        )
        transport.set_response(
            SKILLS_1,
            _sitemap(
                f"{BASE}/one/repo/first",
                f"{BASE}/two/repo/second",
            ),
        )

        results = list(SkillsShAdapter(transport).discover(BASE, limit=1))

        assert len(results) == 1
        assert f"GET {SKILLS_2}" not in transport.call_log

    def test_invalid_sitemap_xml_is_reported(self) -> None:
        transport = _transport()
        transport.set_response(INDEX, HttpResponse(200, b"not-xml"))

        with pytest.raises(RuntimeError, match="invalid XML"):
            list(SkillsShAdapter(transport).discover(BASE))

    def test_robots_disallow_is_reported(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            ROBOTS,
            HttpResponse(200, b"User-agent: *\nDisallow: /sitemap.xml\n"),
        )

        with pytest.raises(PermissionError, match=r"blocked by robots\.txt"):
            list(SkillsShAdapter(transport).discover(BASE))

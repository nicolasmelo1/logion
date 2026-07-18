"""Tests for the browse.sh sitemap adapter."""

from __future__ import annotations

import pytest

from logion_indexer.adapters.browse_sh import BrowseShAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

BASE = "https://browse.sh"
ROBOTS = f"{BASE}/robots.txt"
SITEMAP = f"{BASE}/sitemap.xml"


def _sitemap(*urls: str) -> HttpResponse:
    body = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
    return HttpResponse(200, f"<urlset>{body}</urlset>".encode())


def _transport() -> FakeTransport:
    transport = FakeTransport()
    transport.set_response(ROBOTS, HttpResponse(200, b""))
    return transport


class TestBrowseShAdapter:
    def test_emits_official_repo_when_sitemap_lists_skills(self) -> None:
        transport = _transport()
        transport.set_response(
            SITEMAP,
            _sitemap(
                BASE,
                f"{BASE}/skills/example.com/search-products",
                f"{BASE}/skills/docs.example/read-page",
                "https://browse.sh:444/skills/evil/injected",
                "https://evil.example/skills/evil/injected",
            ),
        )

        results = list(BrowseShAdapter(transport).discover(f"{BASE}/"))

        assert len(results) == 1
        skill = results[0]
        assert str(skill.canonical) == "gh:browserbase/browse.sh"
        assert skill.channels[0].hub_verified is True
        assert dict(skill.channels[0].metadata) == {"catalogEntries": "2"}

    def test_no_skill_urls_returns_no_discovery(self) -> None:
        transport = _transport()
        transport.set_response(SITEMAP, _sitemap(BASE, f"{BASE}/about"))

        assert list(BrowseShAdapter(transport).discover(BASE)) == []

    def test_zero_limit_does_not_fetch(self) -> None:
        transport = _transport()

        assert list(BrowseShAdapter(transport).discover(BASE, limit=0)) == []
        assert transport.call_log == []

    def test_invalid_sitemap_is_reported(self) -> None:
        transport = _transport()
        transport.set_response(SITEMAP, HttpResponse(200, b"not-xml"))

        with pytest.raises(RuntimeError, match="invalid XML"):
            list(BrowseShAdapter(transport).discover(BASE))

    def test_robots_disallow_is_reported(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            ROBOTS,
            HttpResponse(200, b"User-agent: *\nDisallow: /sitemap.xml\n"),
        )

        with pytest.raises(PermissionError, match=r"blocked by robots\.txt"):
            list(BrowseShAdapter(transport).discover(BASE))

"""Tests for browse.sh adapter: fixture-driven parsing, robots."""

from __future__ import annotations

from logion_indexer.adapters.browse_sh import BrowseShAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

BROWSE_SH_HTML = """
<html><body>
  <a href="/skill/1" class="listing">
    <h3>My Skill</h3>
    <a href="https://github.com/octocat/my-skill">GitHub</a>
  </a>
</body></html>
"""


class TestBrowseShAdapter:
    def test_parse_listings(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://browse.sh/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://browse.sh",
            HttpResponse(200, BROWSE_SH_HTML.encode()),
        )
        adapter = BrowseShAdapter(transport)
        results = list(adapter.discover("https://browse.sh/"))
        assert len(results) >= 1
        assert results[0].canonical.owner == "octocat"
        assert results[0].canonical.repo == "my-skill"

    def test_no_github_dropped(self) -> None:
        html = '<a href="/x" class="listing"><h3>No GitHub</h3></a>'
        transport = FakeTransport()
        transport.set_response(
            "https://browse.sh/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://browse.sh",
            HttpResponse(200, html.encode()),
        )
        adapter = BrowseShAdapter(transport)
        results = list(adapter.discover("https://browse.sh/"))
        assert len(results) == 0

    def test_robots_disallow(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://browse.sh/robots.txt",
            HttpResponse(200, b"User-agent: *\nDisallow: /\n"),
        )
        transport.set_response(
            "https://browse.sh",
            HttpResponse(200, BROWSE_SH_HTML.encode()),
        )
        adapter = BrowseShAdapter(transport)
        results = list(adapter.discover("https://browse.sh/"))
        assert len(results) == 0

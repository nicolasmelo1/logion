"""Tests for clawhub adapter: fixture-driven parsing, robots, rate limiter."""

from __future__ import annotations

from logion_indexer.adapters.clawhub import ClawhubAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

CLAWHUB_HTML = """
<html><body>
  <div class="skill-card">
    <h3>Awesome Skill</h3>
    <a href="https://github.com/octocat/awesome">GitHub</a>
  </div>
  <div class="skill-card verified">
    <h3>Verified Skill</h3>
    <a href="https://github.com/anthropics/skills">GitHub</a>
  </div>
</body></html>
"""


class TestClawhubAdapter:
    def test_parse_skill_cards(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://clawhub.ai/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://clawhub.ai",
            HttpResponse(200, CLAWHUB_HTML.encode()),
        )
        adapter = ClawhubAdapter(transport)
        results = list(adapter.discover("https://clawhub.ai/"))
        assert len(results) >= 1
        titles = [r.title for r in results]
        assert "Awesome Skill" in titles

    def test_verified_flag(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://clawhub.ai/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://clawhub.ai",
            HttpResponse(200, CLAWHUB_HTML.encode()),
        )
        adapter = ClawhubAdapter(transport)
        results = list(adapter.discover("https://clawhub.ai/"))
        verified = [r for r in results if r.channels[0].hub_verified]
        assert len(verified) >= 1

    def test_no_github_source_dropped(self) -> None:
        html = """
        <div class="skill-card">
          <h3>No Link Skill</h3>
        </div>
        """
        transport = FakeTransport()
        transport.set_response(
            "https://clawhub.ai/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://clawhub.ai",
            HttpResponse(200, html.encode()),
        )
        adapter = ClawhubAdapter(transport)
        results = list(adapter.discover("https://clawhub.ai/"))
        assert len(results) == 0

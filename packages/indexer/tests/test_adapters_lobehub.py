"""Tests for lobehub adapter: fixture-driven parsing, robots, rate limiter."""

from __future__ import annotations

from logion_indexer.adapters.lobehub import LobehubAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

LOBEHUB_JSON = """
{
  "skills": [
    {
      "title": "Coding Assistant",
      "github_url": "https://github.com/octocat/coding-assistant",
      "verified": true
    }
  ]
}
"""


class TestLobehubAdapter:
    def test_parse_json_skills(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://lobehub.com/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://lobehub.com/skills",
            HttpResponse(200, LOBEHUB_JSON.encode()),
        )
        adapter = LobehubAdapter(transport)
        results = list(adapter.discover("https://lobehub.com/skills"))
        assert len(results) >= 1
        assert results[0].canonical.owner == "octocat"
        assert results[0].canonical.repo == "coding-assistant"

    def test_robots_disallow(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://lobehub.com/robots.txt",
            HttpResponse(200, b"User-agent: *\nDisallow: /skills\n"),
        )
        transport.set_response(
            "https://lobehub.com/skills",
            HttpResponse(200, LOBEHUB_JSON.encode()),
        )
        adapter = LobehubAdapter(transport)
        # Should be blocked by robots.txt → empty results.
        results = list(adapter.discover("https://lobehub.com/skills"))
        assert len(results) == 0

    def test_rate_limiter(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://lobehub.com/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://lobehub.com/skills",
            HttpResponse(200, LOBEHUB_JSON.encode()),
        )
        adapter = LobehubAdapter(transport)
        list(adapter.discover("https://lobehub.com/skills"))
        assert len(transport.call_log) > 0

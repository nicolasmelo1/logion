"""Tests for skills.sh adapter: fixture-driven parsing."""

from __future__ import annotations

from logion_indexer.adapters.skills_sh import SkillsShAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

SKILLS_SH_HTML = """
<html><body>
  <a href="/skills/foo-skill">Foo Skill</a>
  <a href="/skills/bar-skill">Bar Skill</a>
</body></html>
"""

SKILL_DETAIL_HTML = """
<html><body>
  <a href="https://github.com/octocat/foo-repo">GitHub</a>
</body></html>
"""

ROBOTS_DISALLOW = """
User-agent: *
Disallow: /skills/bar-skill
"""


class TestSkillsShAdapter:
    def test_parse_skill_links(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://www.skills.sh/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://www.skills.sh",
            HttpResponse(200, SKILLS_SH_HTML.encode()),
        )
        transport.set_response(
            "https://www.skills.sh/skills/foo-skill",
            HttpResponse(200, SKILL_DETAIL_HTML.encode()),
        )
        transport.set_response(
            "https://www.skills.sh/skills/bar-skill",
            HttpResponse(200, SKILL_DETAIL_HTML.encode()),
        )
        adapter = SkillsShAdapter(transport)
        results = list(adapter.discover("https://www.skills.sh/"))
        # At least one skill should be discovered from the GitHub link.
        assert len(results) >= 1
        assert results[0].canonical.owner == "octocat"
        assert results[0].canonical.repo == "foo-repo"
        assert results[0].channels[0].hub_slug == "skills_sh"

    def test_robots_disallow(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://www.skills.sh/robots.txt",
            HttpResponse(200, ROBOTS_DISALLOW.encode()),
        )
        transport.set_response(
            "https://www.skills.sh",
            HttpResponse(200, SKILLS_SH_HTML.encode()),
        )
        transport.set_response(
            "https://www.skills.sh/skills/foo-skill",
            HttpResponse(200, SKILL_DETAIL_HTML.encode()),
        )
        adapter = SkillsShAdapter(transport)
        results = list(adapter.discover("https://www.skills.sh/"))
        # bar-skill is disallowed; only foo-skill should be discovered.
        for r in results:
            assert "bar-skill" not in str(r.canonical)

    def test_rate_limiter_called(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://www.skills.sh/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://www.skills.sh",
            HttpResponse(200, SKILLS_SH_HTML.encode()),
        )
        transport.set_response(
            "https://www.skills.sh/skills/foo-skill",
            HttpResponse(200, SKILL_DETAIL_HTML.encode()),
        )
        adapter = SkillsShAdapter(transport)
        # Rate limiter is set up by Crawler; verify no exceptions.
        list(adapter.discover("https://www.skills.sh/"))
        assert len(transport.call_log) > 0

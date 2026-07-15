"""Tests for hermes_docs adapter: fixture-driven parsing."""

from __future__ import annotations

from logion_indexer.adapters.hermes_docs import HermesDocsAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

HERMES_DOCS_HTML = """
<html><body>
  <h1 id="skills">Skills</h1>
  <p>Check out <a href="https://github.com/nousresearch/hermes">Hermes</a></p>
  <p>And <a href="https://github.com/openai/codex">Codex</a></p>
</body></html>
"""


class TestHermesDocsAdapter:
    def test_parse_github_links(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://hermes-agent.nousresearch.com/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://hermes-agent.nousresearch.com/docs/skills",
            HttpResponse(200, HERMES_DOCS_HTML.encode()),
        )
        adapter = HermesDocsAdapter(transport)
        results = list(
            adapter.discover(
                "https://hermes-agent.nousresearch.com/docs/skills"
            )
        )
        assert len(results) >= 1
        owners = {r.canonical.owner for r in results}
        assert "nousresearch" in owners
        assert "openai" in owners

    def test_dedup_same_repo(self) -> None:
        html = """
        <a href="https://github.com/nousresearch/hermes">Hermes</a>
        <a href="https://github.com/NousResearch/Hermes">Hermes2</a>
        """
        transport = FakeTransport()
        transport.set_response(
            "https://hermes-agent.nousresearch.com/robots.txt",
            HttpResponse(200, b""),
        )
        transport.set_response(
            "https://hermes-agent.nousresearch.com/docs/skills",
            HttpResponse(200, html.encode()),
        )
        adapter = HermesDocsAdapter(transport)
        results = list(
            adapter.discover(
                "https://hermes-agent.nousresearch.com/docs/skills"
            )
        )
        # Same repo (after lowercasing) → deduped to 1.
        assert len(results) == 1

    def test_robots_disallow(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://hermes-agent.nousresearch.com/robots.txt",
            HttpResponse(200, b"User-agent: *\nDisallow: /docs\n"),
        )
        transport.set_response(
            "https://hermes-agent.nousresearch.com/docs/skills",
            HttpResponse(200, HERMES_DOCS_HTML.encode()),
        )
        adapter = HermesDocsAdapter(transport)
        results = list(
            adapter.discover(
                "https://hermes-agent.nousresearch.com/docs/skills"
            )
        )
        assert len(results) == 0

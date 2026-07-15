"""Tests for github_resolver: extraction from hub page fixtures."""

from __future__ import annotations

from logion_indexer.github_resolver import (
    resolve_github_url,
    resolve_hub_page,
)


class TestResolveHubPage:
    def test_extract_from_href(self) -> None:
        html = (
            '<a href="https://github.com/octocat/hello-world">'
            "View on GitHub</a>"
        )
        result = resolve_hub_page("https://hub.example.com/skill/1", html)
        assert result.resolved
        assert result.canonical is not None
        assert result.canonical.owner == "octocat"
        assert result.canonical.repo == "hello-world"

    def test_extract_with_subpath(self) -> None:
        html = (
            '<a href="https://github.com/octocat/hello-world/'
            'tree/main/skills/foo">GitHub</a>'
        )
        result = resolve_hub_page("https://hub.example.com/skill/1", html)
        assert result.resolved
        assert result.canonical is not None
        assert result.canonical.owner == "octocat"
        assert result.canonical.repo == "hello-world"
        assert result.canonical.subpath == "skills/foo"

    def test_no_github_source_drop(self) -> None:
        html = "<div>No GitHub link here</div>"
        result = resolve_hub_page("https://hub.example.com/skill/1", html)
        assert not result.resolved
        assert result.canonical is None
        assert result.reason == "no_github_source"

    def test_skip_issues_link(self) -> None:
        html = (
            '<a href="https://github.com/octocat/hello-world/issues">'
            "Issues</a>"
        )
        result = resolve_hub_page("https://hub.example.com/skill/1", html)
        assert not result.resolved
        assert result.reason == "no_github_source"

    def test_skip_pulls_link(self) -> None:
        html = '<a href="https://github.com/octocat/hello-world/pulls">PRs</a>'
        result = resolve_hub_page("https://hub.example.com/skill/1", html)
        assert not result.resolved

    def test_text_fallback(self) -> None:
        html = "Check out github.com/octocat/hello-world for details"
        result = resolve_hub_page("https://hub.example.com/skill/1", html)
        assert result.resolved
        assert result.canonical is not None
        assert result.canonical.owner == "octocat"
        assert result.canonical.repo == "hello-world"


class TestResolveGithubUrl:
    def test_direct_url(self) -> None:
        result = resolve_github_url("https://github.com/octocat/hello-world")
        assert result.resolved
        assert result.canonical is not None
        assert result.canonical.owner == "octocat"

    def test_non_github_url(self) -> None:
        result = resolve_github_url("https://example.com/something")
        assert not result.resolved
        assert result.reason == "no_github_source"

"""Tests for hub-discovery enrichment: map attachment, expansion, skips."""

from __future__ import annotations

import json
from http.client import RemoteDisconnected

from logion_indexer.canonical import CanonicalSkillId
from logion_indexer.enrichment import (
    SKIP_GITHUB_NETWORK_ERROR,
    SKIP_NO_COMPONENTS,
    SKIP_NO_GITHUB_SOURCE,
    enrich_discoveries,
)
from logion_indexer.github_source import GithubSource
from logion_indexer.models import DiscoveredSkill, DiscoveryChannel
from logion_indexer.transport import FakeTransport, HttpResponse

REPO_META = {
    "default_branch": "main",
    "license": {"spdx_id": "MIT"},
    "size": 5,
}
BRANCH_INFO = {"commit": {"sha": "abc123"}}
REPO_TREE = {
    "tree": [
        {"path": "skills/foo/SKILL.md", "type": "blob", "size": 500},
        {"path": "skills/bar/SKILL.md", "type": "blob", "size": 500},
    ]
}
CONTENTS_FOO = {
    "content": (
        "LS0tCm5hbWU6IGZvbwpkZXNjcmlwdGlvbjogQSBmb28gc2tpbGwKLS0tCiMgRm9vIFNraWxsCg=="
    ),
    "encoding": "base64",
}
CONTENTS_BAR = {
    "content": (
        "LS0tCm5hbWU6IGJhcgpkZXNjcmlwdGlvbjogQSBiYXIgc2tpbGwKLS0tCiMgQmFyIFNraWxsCg=="
    ),
    "encoding": "base64",
}


def _wire_repo(transport: FakeTransport) -> None:
    transport.set_response(
        "https://api.github.com/repos/octocat/hello",
        HttpResponse(200, json.dumps(REPO_META).encode()),
    )
    transport.set_response(
        "https://api.github.com/repos/octocat/hello/branches/main",
        HttpResponse(200, json.dumps(BRANCH_INFO).encode()),
    )
    transport.set_response(
        "https://api.github.com/repos/octocat/hello/git/trees/abc123?recursive=1",
        HttpResponse(200, json.dumps(REPO_TREE).encode()),
    )
    transport.set_response(
        "https://api.github.com/repos/octocat/hello/contents/skills/foo/SKILL.md?ref=abc123",
        HttpResponse(200, json.dumps(CONTENTS_FOO).encode()),
    )
    transport.set_response(
        "https://api.github.com/repos/octocat/hello/contents/skills/bar/SKILL.md?ref=abc123",
        HttpResponse(200, json.dumps(CONTENTS_BAR).encode()),
    )


def _hub_discovery() -> DiscoveredSkill:
    return DiscoveredSkill(
        canonical=CanonicalSkillId(owner="octocat", repo="hello"),
        title="hub-title",
        original_author="octocat",
        channels=(
            DiscoveryChannel(
                hub_slug="clawhub",
                hub_url="https://clawhub.ai/skills/octocat/hello",
                hub_verified=True,
            ),
        ),
        inferred_map=None,
    )


class TestEnrichment:
    def test_inference_encodes_content_path(self) -> None:
        transport = FakeTransport()
        source = GithubSource(transport=transport)
        url = (
            "https://api.github.com/repos/octocat/hello/contents/"
            ".agents/skills/Financial%20Data%20Fetcher/SKILL.md?ref=abc123"
        )
        transport.set_response(
            url,
            HttpResponse(
                200,
                json.dumps({
                    "content": "c2tpbGw=",
                    "encoding": "base64",
                }).encode(),
            ),
        )

        fetch_blob = source._make_blob_fetcher("octocat", "hello", "abc123")

        path = ".agents/skills/Financial Data Fetcher/SKILL.md"
        assert fetch_blob(path) == b"skill"

    def test_attaches_non_null_maps(self) -> None:
        transport = FakeTransport()
        _wire_repo(transport)
        source = GithubSource(transport=transport)
        items, skips = enrich_discoveries([_hub_discovery()], source)
        assert skips == []
        assert len(items) == 2
        for item in items:
            assert item.inferred_map is not None
            assert item.inferred_map["version"] == 1

    def test_expands_per_component(self) -> None:
        transport = FakeTransport()
        _wire_repo(transport)
        source = GithubSource(transport=transport)
        items, _ = enrich_discoveries([_hub_discovery()], source)
        subpaths = {item.canonical.subpath for item in items}
        assert subpaths == {"skills/foo", "skills/bar"}

    def test_unions_hub_channels(self) -> None:
        transport = FakeTransport()
        _wire_repo(transport)
        source = GithubSource(transport=transport)
        items, _ = enrich_discoveries([_hub_discovery()], source)
        for item in items:
            assert len(item.channels) == 1
            assert item.channels[0].hub_slug == "clawhub"
            assert item.channels[0].hub_verified is True

    def test_frontmatter_title_over_hub_text(self) -> None:
        transport = FakeTransport()
        _wire_repo(transport)
        source = GithubSource(transport=transport)
        items, _ = enrich_discoveries([_hub_discovery()], source)
        titles = {item.title for item in items}
        assert titles == {"foo", "bar"}

    def test_already_mapped_passes_through(self) -> None:
        mapped = DiscoveredSkill(
            canonical=CanonicalSkillId(owner="o", repo="r", subpath="s"),
            inferred_map={"version": 1, "package": {"slug": "s"}},
        )
        source = GithubSource(transport=FakeTransport())
        items, skips = enrich_discoveries([mapped], source)
        assert items == [mapped]
        assert skips == []

    def test_no_github_source_skip(self) -> None:
        # No repo wired → HEAD sha lookup fails → dropped.
        transport = FakeTransport()
        source = GithubSource(transport=transport)
        items, skips = enrich_discoveries([_hub_discovery()], source)
        assert items == []
        assert len(skips) == 1
        assert skips[0]["reason"] == SKIP_NO_GITHUB_SOURCE
        assert skips[0]["canonical"] == "gh:octocat/hello"

    def test_network_error_during_inference_is_recorded_as_skip(
        self, monkeypatch
    ) -> None:
        source = GithubSource(transport=FakeTransport())
        monkeypatch.setattr(source, "fetch_head_sha", lambda *_: "abc123")
        monkeypatch.setattr(source, "fetch_license", lambda *_: "MIT")
        monkeypatch.setattr(
            source,
            "infer_skills",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RemoteDisconnected("closed")
            ),
        )

        items, skips = enrich_discoveries([_hub_discovery()], source)

        assert items == []
        assert skips == [
            {
                "canonical": "gh:octocat/hello",
                "reason": SKIP_GITHUB_NETWORK_ERROR,
            }
        ]

    def test_no_components_skip(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://api.github.com/repos/octocat/hello",
            HttpResponse(200, json.dumps(REPO_META).encode()),
        )
        transport.set_response(
            "https://api.github.com/repos/octocat/hello/branches/main",
            HttpResponse(200, json.dumps(BRANCH_INFO).encode()),
        )
        transport.set_response(
            "https://api.github.com/repos/octocat/hello/git/trees/abc123?recursive=1",
            HttpResponse(200, json.dumps({"tree": []}).encode()),
        )
        source = GithubSource(transport=transport)
        items, skips = enrich_discoveries([_hub_discovery()], source)
        assert items == []
        assert len(skips) == 1
        assert skips[0]["reason"] == SKIP_NO_COMPONENTS

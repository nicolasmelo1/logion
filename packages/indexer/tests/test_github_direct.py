"""Tests for github_direct adapter: repo, subpath, owner modes."""

from __future__ import annotations

import json

from logion_indexer.adapters.github_direct import GithubDirectAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

REPO_META = {
    "default_branch": "main",
    "license": {"spdx_id": "MIT"},
    "size": 500,
}

BRANCH_INFO = {"commit": {"sha": "abc123"}}

REPO_TREE = {
    "tree": [
        {"path": "README.md", "type": "blob", "size": 100},
        {"path": "LICENSE", "type": "blob", "size": 1000},
        {"path": "skills/foo/SKILL.md", "type": "blob", "size": 500},
        {"path": "skills/bar/SKILL.md", "type": "blob", "size": 500},
    ]
}

SKILL_MD_CONTENT = b"""---
name: foo
description: A foo skill
---
# Foo Skill
"""

SKILL_MD_BAR_CONTENT = b"""---
name: bar
description: A bar skill
---
# Bar Skill
"""

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


def _setup_github_responses(transport: FakeTransport) -> None:
    """Wire up the fake transport with GitHub API responses."""
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


class TestRepoMode:
    def test_repo_mode_multi_skill(self) -> None:
        transport = FakeTransport()
        _setup_github_responses(transport)
        adapter = GithubDirectAdapter(transport=transport)
        results = list(adapter.discover("octocat/hello", mode="repo"))
        # Two SKILL.md files → two canonical components.
        assert len(results) == 2
        titles = {r.title for r in results}
        assert "foo" in titles
        assert "bar" in titles

    def test_license_spdx(self) -> None:
        transport = FakeTransport()
        _setup_github_responses(transport)
        adapter = GithubDirectAdapter(transport=transport)
        results = list(adapter.discover("octocat/hello", mode="repo"))
        for r in results:
            assert r.license_spdx == "MIT"

    def test_source_commit(self) -> None:
        transport = FakeTransport()
        _setup_github_responses(transport)
        adapter = GithubDirectAdapter(transport=transport)
        results = list(adapter.discover("octocat/hello", mode="repo"))
        for r in results:
            assert r.source_commit == "abc123"


class TestSubpathMode:
    def test_subpath_filtering(self) -> None:
        transport = FakeTransport()
        _setup_github_responses(transport)
        adapter = GithubDirectAdapter(transport=transport)
        results = list(
            adapter.discover(
                "octocat/hello",
                mode="repo_subpath",
                subpath="skills/foo",
            )
        )
        # Only the foo component should be returned.
        assert len(results) == 1
        assert "foo" in str(results[0].canonical)


class TestInferenceCache:
    def test_cache_single_infer_call(self) -> None:
        transport = FakeTransport()
        _setup_github_responses(transport)
        adapter = GithubDirectAdapter(transport=transport)

        # First discovery.
        list(adapter.discover("octocat/hello", mode="repo"))
        tree_calls_1 = [c for c in transport.call_log if "git/trees" in c]
        assert len(tree_calls_1) == 1

        # Second discovery of the same repo — should use cache.
        list(adapter.discover("octocat/hello", mode="repo"))
        tree_calls_2 = [c for c in transport.call_log if "git/trees" in c]
        # Still only 1 tree call — cached.
        assert len(tree_calls_2) == 1


class TestOwnerMode:
    def test_owner_enum_repos(self) -> None:
        transport = FakeTransport()
        # List repos for owner.
        transport.set_response(
            "https://api.github.com/users/octocat/repos?per_page=100&sort=updated&page=1",
            HttpResponse(
                200,
                json.dumps([
                    {"name": "hello", "license": {"spdx_id": "MIT"}},
                ]).encode(),
            ),
        )
        _setup_github_responses(transport)
        adapter = GithubDirectAdapter(transport=transport)
        results = list(adapter.discover("octocat", mode="owner", limit=5))
        assert len(results) >= 1

    def test_owner_enum_paginates_repos(self) -> None:
        transport = FakeTransport()
        page_1 = (
            "https://api.github.com/users/octocat/repos"
            "?per_page=100&sort=updated&page=1"
        )
        page_2 = (
            "https://api.github.com/users/octocat/repos"
            "?per_page=100&sort=updated&page=2"
        )
        transport.set_response(
            page_1,
            HttpResponse(200, json.dumps([{}] * 100).encode()),
        )
        transport.set_response(
            page_2,
            HttpResponse(
                200,
                json.dumps([
                    {"name": "hello", "license": {"spdx_id": "MIT"}},
                ]).encode(),
            ),
        )
        _setup_github_responses(transport)

        results = list(
            GithubDirectAdapter(transport=transport).discover(
                "octocat",
                mode="owner",
            )
        )

        assert len(results) >= 1
        assert f"GET {page_2}" in transport.call_log


class TestMirrorSubtree:
    def test_runtime_include_matches_subtree(self) -> None:
        transport = FakeTransport()
        _setup_github_responses(transport)
        adapter = GithubDirectAdapter(transport=transport)
        results = list(adapter.discover("octocat/hello", mode="repo"))
        for r in results:
            assert r.inferred_map is not None
            includes = (
                r.inferred_map
                .get("components", {})
                .get("runtime", {})
                .get("include", [])
            )
            assert len(includes) >= 1
            # Each include pattern should cover the component root.
            root = r.canonical.subpath
            if root:
                assert any(root in pattern for pattern in includes)

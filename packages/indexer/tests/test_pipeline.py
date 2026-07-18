"""Tests for the indexing pipeline: invalid-map drops, mirror, lock drift."""

from __future__ import annotations

import io
import tarfile
from unittest.mock import patch
from urllib.error import URLError

from logion_indexer.canonical import CanonicalSkillId
from logion_indexer.github_source import GithubSource
from logion_indexer.mirror import BUNDLE_SKIP_NO_TARBALL
from logion_indexer.models import DiscoveredSkill, DiscoveryChannel
from logion_indexer.pipeline import build_indexing_plan
from logion_indexer.transport import FakeTransport, HttpResponse
from logion_indexer.validation import INFERRED_MAP_INVALID

BASE = "https://api.logion.sh"

FRAGMENT = {
    "version": 1,
    "package": {"slug": "foo"},
    "components": {
        "capabilities": {"foo": {"entrypoint": "skills/foo/SKILL.md"}},
        "runtime": {
            "include": ["skills/foo/**"],
            "entrypoint": "skills/foo/SKILL.md",
        },
    },
}


def _tarball() -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tar:
        blob = b"foo skill body"
        info = tarfile.TarInfo(name="octocat-hello-abc/skills/foo/SKILL.md")
        info.size = len(blob)
        tar.addfile(info, io.BytesIO(blob))
    return raw.getvalue()


class TestInvalidMapDropsRunPartial:
    def test_invalid_map_dropped_and_partial(self) -> None:
        bad = DiscoveredSkill(
            canonical=CanonicalSkillId(owner="o", repo="r", subpath="s"),
            inferred_map={"version": 99, "package": {}, "components": {}},
        )
        transport = FakeTransport()
        source = GithubSource(transport=transport)
        plan, _ = build_indexing_plan(
            [bad], transport, BASE, source=source, mirror=False
        )
        assert plan.create == []
        assert plan.partial is True
        assert any(s["reason"] == INFERRED_MAP_INVALID for s in plan.skip)


class TestMirrorAndLockDrift:
    def test_permissive_bundle_and_lock_drift(self) -> None:
        skill = DiscoveredSkill(
            canonical=CanonicalSkillId(
                owner="octocat", repo="hello", subpath="skills/foo"
            ),
            title="foo",
            original_author="octocat",
            license_spdx="MIT",
            source_commit="abc123",
            channels=(
                DiscoveryChannel(
                    hub_slug="skills_lock",
                    hub_url="https://example.com/skills-lock.json",
                    metadata=(("computedHash", "sha256:stale"),),
                ),
            ),
            inferred_map=FRAGMENT,
        )
        transport = FakeTransport()
        transport.set_response(
            "https://api.github.com/repos/octocat/hello/tarball/abc123",
            HttpResponse(200, _tarball()),
        )
        source = GithubSource(transport=transport)
        plan, artifacts = build_indexing_plan(
            [skill], transport, BASE, source=source, mirror=True
        )
        assert len(plan.create) == 1
        item = plan.create[0]
        # Bundle metadata attached and bytes captured for upload.
        assert item.bundle is not None
        assert item.bundle["sha256"].startswith("sha256:")
        assert str(item.canonical) in artifacts
        # Lock drift flagged on the skills_lock channel (hash mismatch).
        meta = dict(item.channels[0].metadata)
        assert meta.get("lock_drift") == "true"

    def test_restricted_license_no_bundle(self) -> None:
        skill = DiscoveredSkill(
            canonical=CanonicalSkillId(
                owner="octocat", repo="hello", subpath="skills/foo"
            ),
            license_spdx="GPL-3.0",
            source_commit="abc123",
            inferred_map=FRAGMENT,
        )
        transport = FakeTransport()
        source = GithubSource(transport=transport)
        with patch.object(source, "fetch_tarball") as fetch_tarball:
            plan, artifacts = build_indexing_plan(
                [skill], transport, BASE, source=source, mirror=True
            )
        fetch_tarball.assert_not_called()
        assert len(plan.create) == 1
        assert plan.create[0].bundle is None
        assert artifacts == {}

    def test_tarball_network_failure_keeps_listing_link_only(self) -> None:
        skill = DiscoveredSkill(
            canonical=CanonicalSkillId(
                owner="octocat", repo="hello", subpath="skills/foo"
            ),
            license_spdx="MIT",
            source_commit="abc123",
            inferred_map=FRAGMENT,
        )
        transport = FakeTransport()
        source = GithubSource(transport=transport)

        with patch.object(
            source,
            "fetch_tarball",
            side_effect=URLError("timed out"),
        ):
            plan, artifacts = build_indexing_plan(
                [skill], transport, BASE, source=source, mirror=True
            )

        assert len(plan.create) == 1
        assert plan.create[0].bundle is None
        assert BUNDLE_SKIP_NO_TARBALL in plan.create[0].map_flags
        assert artifacts == {}

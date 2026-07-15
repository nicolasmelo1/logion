"""Tests for dedup: multi-hub collapse, known-map, plan output, dry-run."""

from __future__ import annotations

from logion_indexer.canonical import CanonicalSkillId
from logion_indexer.dedup import (
    build_plan,
    dry_run_plan,
    merge_discoveries,
)
from logion_indexer.models import DiscoveredSkill, DiscoveryChannel
from logion_indexer.transport import FakeTransport, HttpResponse


def _make_skill(
    owner: str = "octocat",
    repo: str = "hello",
    subpath: str = "",
    *,
    channels: tuple[DiscoveryChannel, ...] = (),
    title: str = "",
) -> DiscoveredSkill:
    return DiscoveredSkill(
        canonical=CanonicalSkillId(owner=owner, repo=repo, subpath=subpath),
        title=title,
        channels=channels,
        original_author=owner,
    )


class TestMergeDiscoveries:
    def test_multi_hub_collapse(self) -> None:
        CanonicalSkillId(owner="octocat", repo="hello")
        ch1 = DiscoveryChannel(
            hub_slug="lobehub", hub_url="https://lobehub.com/1"
        )
        ch2 = DiscoveryChannel(
            hub_slug="clawhub", hub_url="https://clawhub.ai/2"
        )
        ch3 = DiscoveryChannel(
            hub_slug="skills_sh", hub_url="https://skills.sh/3"
        )

        d1 = _make_skill(channels=(ch1,))
        d2 = _make_skill(channels=(ch2,))
        d3 = _make_skill(channels=(ch3,))

        merged = merge_discoveries([d1, d2, d3])
        assert len(merged) == 1
        assert len(merged[0].channels) == 3

    def test_different_skills_stay_separate(self) -> None:
        d1 = _make_skill(owner="aaa", repo="repo")
        d2 = _make_skill(owner="bbb", repo="repo")
        merged = merge_discoveries([d1, d2])
        assert len(merged) == 2

    def test_union_tags(self) -> None:
        d1 = _make_skill()
        d1_with_tags = DiscoveredSkill(
            canonical=d1.canonical,
            tags=("coding", "python"),
            channels=(DiscoveryChannel("hub", "url"),),
            original_author="octocat",
        )
        d2 = _make_skill()
        d2_with_tags = DiscoveredSkill(
            canonical=d2.canonical,
            tags=("coding", "testing"),
            channels=(DiscoveryChannel("hub2", "url2"),),
            original_author="octocat",
        )
        merged = merge_discoveries([d1_with_tags, d2_with_tags])
        assert len(merged) == 1
        assert set(merged[0].tags) == {"coding", "python", "testing"}


class TestKnownMap:
    def test_update_existing_listing(self) -> None:
        merged = [_make_skill()]
        known = {"gh:octocat/hello": {"kind": "indexed_listing", "id": "abc"}}
        plan = build_plan(merged, known)
        assert len(plan.update) == 1
        assert len(plan.create) == 0

    def test_skip_course(self) -> None:
        merged = [_make_skill()]
        known = {"gh:octocat/hello": {"kind": "course", "id": "course-1"}}
        plan = build_plan(merged, known)
        assert len(plan.skip) == 1
        assert plan.skip[0]["reason"] == "already_logion_course"

    def test_skip_claimed(self) -> None:
        merged = [_make_skill()]
        known = {"gh:octocat/hello": {"kind": "claimed", "id": "claim-1"}}
        plan = build_plan(merged, known)
        assert len(plan.skip) == 1
        assert plan.skip[0]["reason"] == "already_claimed"

    def test_create_when_absent(self) -> None:
        merged = [_make_skill()]
        plan = build_plan(merged, {})
        assert len(plan.create) == 1
        assert len(plan.skip) == 0


class TestPlanOutput:
    def test_plan_shape(self) -> None:
        d1 = _make_skill(owner="aaa", repo="r1")
        d2 = _make_skill(owner="bbb", repo="r2")
        known = {"gh:bbb/r2": {"kind": "course", "id": "c1"}}
        plan = build_plan([d1, d2], known)
        d = plan.to_dict()
        assert "create" in d
        assert "update" in d
        assert "skip" in d
        assert len(d["create"]) == 1
        assert len(d["skip"]) == 1


class TestDryRun:
    def test_dry_run_zero_posts(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://api.logion.sh/v1/admin/indexing/known"
            "?ids=gh%3Aoctocat%2Fhello",
            HttpResponse(200, b'{"known": {}}'),
        )
        d = _make_skill()
        plan = dry_run_plan([d], transport, "https://api.logion.sh")
        assert len(plan.create) == 1
        # No POST calls should have been made.
        posts = [c for c in transport.call_log if c.startswith("POST")]
        assert len(posts) == 0

    def test_dry_run_queries_get(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://api.logion.sh/v1/admin/indexing/known"
            "?ids=gh%3Aoctocat%2Fhello",
            HttpResponse(200, b'{"known": {}}'),
        )
        d = _make_skill()
        dry_run_plan([d], transport, "https://api.logion.sh")
        gets = [c for c in transport.call_log if c.startswith("GET")]
        assert len(gets) >= 1

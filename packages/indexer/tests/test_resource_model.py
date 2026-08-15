# SPDX-License-Identifier: MIT
"""Tests for DiscoveredResource model, resource dedup, and pusher
serialization."""

from __future__ import annotations

import json

import pytest

from logion_indexer.canonical import (
    CanonicalResourceId,
    CanonicalSkillId,
)
from logion_indexer.dedup import (
    build_resource_plan,
    merge_resource_discoveries,
)
from logion_indexer.models import (
    DiscoveredResource,
    DiscoveredSkill,
    DiscoveryChannel,
)
from logion_indexer.pusher import (
    serialize_item,
    serialize_resource_item,
)


def _make_channel(
    slug: str = "hub",
    url: str = "https://hub.test",
) -> DiscoveryChannel:
    return DiscoveryChannel(hub_slug=slug, hub_url=url)


def _make_resource(
    resource_type: str = "skill",
    uri: str = "gh:octocat/hello",
    *,
    title: str = "",
    channels: tuple[DiscoveryChannel, ...] = (),
) -> DiscoveredResource:
    return DiscoveredResource(
        canonical=CanonicalResourceId(resource_type=resource_type, uri=uri),
        resource_type=resource_type,
        canonical_uri=uri,
        title=title,
        channels=channels,
        original_author=(uri.split("/")[-1] if "/" in uri else "unknown"),
    )


class TestDiscoveredResourceModel:
    def test_default_fields(self) -> None:
        rid = CanonicalResourceId(
            resource_type="skill", uri="gh:octocat/hello"
        )
        r = DiscoveredResource(canonical=rid)
        assert r.resource_type == "skill"
        assert r.canonical_uri == ""
        assert r.title == ""
        assert r.summary == ""
        assert r.tags == ()
        assert r.channels == ()
        assert r.inferred_map is None
        assert r.bundle is None

    def test_full_fields(self) -> None:
        rid = CanonicalResourceId(resource_type="plugin", uri="npm:foo")
        ch = _make_channel("npmhub", "https://npmhub.test/foo")
        r = DiscoveredResource(
            canonical=rid,
            resource_type="plugin",
            canonical_uri="npm:foo",
            title="Foo Plugin",
            summary="A test plugin",
            original_author="author",
            license_spdx="MIT",
            tags=("testing", "plugin"),
            channels=(ch,),
        )
        assert r.canonical == rid
        assert r.resource_type == "plugin"
        assert r.canonical_uri == "npm:foo"
        assert r.title == "Foo Plugin"
        assert r.license_spdx == "MIT"

    def test_frozen(self) -> None:
        rid = CanonicalResourceId(resource_type="skill", uri="gh:a/b")
        r = DiscoveredResource(canonical=rid)
        with pytest.raises(AttributeError):
            r.title = "changed"  # type: ignore[misc]


class TestDiscoveredSkillCompatibility:
    def test_to_resource(self) -> None:
        skill = DiscoveredSkill(
            canonical=CanonicalSkillId(owner="octocat", repo="hello"),
            title="Hello Skill",
            summary="A test skill",
            original_author="octocat",
            tags=("python",),
            channels=(_make_channel(),),
        )
        resource = skill.to_resource()
        assert resource.resource_type == "skill"
        assert resource.canonical_uri == "gh:octocat/hello"
        assert resource.title == "Hello Skill"
        assert resource.tags == ("python",)
        assert len(resource.channels) == 1

    def test_from_resource_skill(self) -> None:
        rid = CanonicalResourceId(
            resource_type="skill", uri="gh:octocat/hello"
        )
        resource = DiscoveredResource(
            canonical=rid,
            resource_type="skill",
            canonical_uri="gh:octocat/hello",
            title="Hello Skill",
        )
        skill = DiscoveredSkill.from_resource(resource)
        assert skill.canonical == CanonicalSkillId(
            owner="octocat", repo="hello"
        )
        assert skill.title == "Hello Skill"

    def test_from_resource_rejects_non_skill(self) -> None:
        rid = CanonicalResourceId(resource_type="plugin", uri="npm:foo")
        resource = DiscoveredResource(
            canonical=rid,
            resource_type="plugin",
            canonical_uri="npm:foo",
        )
        with pytest.raises(ValueError, match="Cannot convert"):
            DiscoveredSkill.from_resource(resource)

    def test_round_trip_skill_to_resource_and_back(self) -> None:
        skill = DiscoveredSkill(
            canonical=CanonicalSkillId(
                owner="octocat",
                repo="hello",
                subpath="skills/bar",
            ),
            title="My Skill",
            summary="A great skill",
            original_author="octocat",
            license_spdx="MIT",
            tags=("coding",),
            channels=(
                _make_channel(
                    "gh",
                    "https://github.com/octocat/hello",
                ),
            ),
        )
        resource = skill.to_resource()
        recovered = DiscoveredSkill.from_resource(resource)
        assert recovered.canonical == skill.canonical
        assert recovered.title == skill.title
        assert recovered.summary == skill.summary
        assert recovered.license_spdx == skill.license_spdx
        assert recovered.tags == skill.tags


class TestMergeResourceDiscoveries:
    def test_multi_hub_collapse(self) -> None:
        ch1 = _make_channel("hub_a", "https://a.test/1")
        ch2 = _make_channel("hub_b", "https://b.test/2")
        d1 = _make_resource(channels=(ch1,))
        d2 = _make_resource(channels=(ch2,))
        merged = merge_resource_discoveries([d1, d2])
        assert len(merged) == 1
        assert len(merged[0].channels) == 2

    def test_different_resources_stay_separate(self) -> None:
        d1 = _make_resource(uri="gh:aaa/repo")
        d2 = _make_resource(uri="gh:bbb/repo")
        merged = merge_resource_discoveries([d1, d2])
        assert len(merged) == 2

    def test_mixed_resource_types_stay_separate(self) -> None:
        d1 = _make_resource(resource_type="skill", uri="gh:octocat/hello")
        d2 = _make_resource(resource_type="plugin", uri="npm:hello")
        merged = merge_resource_discoveries([d1, d2])
        assert len(merged) == 2

    def test_union_tags(self) -> None:
        rid = CanonicalResourceId(
            resource_type="skill", uri="gh:octocat/hello"
        )
        d1 = DiscoveredResource(
            canonical=rid,
            resource_type="skill",
            canonical_uri="gh:octocat/hello",
            tags=("coding", "python"),
            channels=(_make_channel("hub", "url"),),
        )
        d2 = DiscoveredResource(
            canonical=rid,
            resource_type="skill",
            canonical_uri="gh:octocat/hello",
            tags=("coding", "testing"),
            channels=(_make_channel("hub2", "url2"),),
        )
        merged = merge_resource_discoveries([d1, d2])
        assert len(merged) == 1
        assert set(merged[0].tags) == {
            "coding",
            "python",
            "testing",
        }


class TestBuildResourcePlan:
    def test_create_when_absent(self) -> None:
        d = _make_resource()
        plan = build_resource_plan([d], {})
        assert len(plan.create) == 1
        assert len(plan.update) == 0
        assert len(plan.skip) == 0

    def test_update_indexed_listing(self) -> None:
        d = _make_resource()
        known = {
            "gh:octocat/hello": {
                "kind": "indexed_listing",
                "id": "abc",
            }
        }
        plan = build_resource_plan([d], known)
        assert len(plan.update) == 1
        assert len(plan.create) == 0

    def test_skip_course(self) -> None:
        d = _make_resource()
        known = {
            "gh:octocat/hello": {
                "kind": "course",
                "id": "c1",
            }
        }
        plan = build_resource_plan([d], known)
        assert len(plan.skip) == 1
        assert plan.skip[0]["reason"] == "already_logion_course"

    def test_skip_claimed(self) -> None:
        d = _make_resource()
        known = {
            "gh:octocat/hello": {
                "kind": "claimed",
                "id": "cl1",
            }
        }
        plan = build_resource_plan([d], known)
        assert len(plan.skip) == 1
        assert plan.skip[0]["reason"] == "already_claimed"


class TestResourceDedupPlanOutput:
    def test_to_dict(self) -> None:
        d = _make_resource(title="Test")
        plan = build_resource_plan([d], {})
        result = plan.to_dict()
        assert "create" in result
        assert "update" in result
        assert "skip" in result
        assert len(result["create"]) == 1

    def test_to_json(self) -> None:
        d = _make_resource(title="Test")
        plan = build_resource_plan([d], {})
        json_str = plan.to_json()
        data = json.loads(json_str)
        assert "create" in data


class TestPusherSerialization:
    def test_skill_serialization_includes_resource_id(
        self,
    ) -> None:
        skill = DiscoveredSkill(
            canonical=CanonicalSkillId(owner="octocat", repo="hello"),
            title="Hello",
            original_author="octocat",
        )
        result = serialize_item(skill)
        assert result["canonical"] == "gh:octocat/hello"
        assert result["resource_id"] == "skill:gh:octocat/hello"
        assert result["title"] == "Hello"

    def test_resource_serialization_includes_resource_type_and_canonical_uri(
        self,
    ) -> None:
        rid = CanonicalResourceId(resource_type="plugin", uri="npm:foo")
        resource = DiscoveredResource(
            canonical=rid,
            resource_type="plugin",
            canonical_uri="npm:foo",
            title="Foo Plugin",
            original_author="author",
        )
        result = serialize_resource_item(resource)
        assert result["canonical"] == "npm:foo"
        assert result["resource_type"] == "plugin"
        assert result["canonical_uri"] == "npm:foo"
        assert result["resource_id"] == "plugin:npm:foo"
        assert result["title"] == "Foo Plugin"

    def test_skill_and_resource_produce_compatible_skill_fields(
        self,
    ) -> None:
        skill = DiscoveredSkill(
            canonical=CanonicalSkillId(owner="octocat", repo="hello"),
            title="Hello",
            summary="A skill",
            original_author="octocat",
            tags=("python",),
        )
        resource = skill.to_resource()
        skill_result = serialize_item(skill)
        resource_result = serialize_resource_item(resource)

        # Skill-compatible fields should match.
        compat_keys = (
            "title",
            "summary",
            "original_author",
            "tags",
            "license_spdx",
        )
        for key in compat_keys:
            assert skill_result[key] == resource_result[key], (
                f"Mismatch on {key}"
            )

        # Resource result has extra keys.
        assert "resource_type" in resource_result
        assert "canonical_uri" in resource_result


class TestKnownLookupVocabulary:
    """The `known` endpoint resolves canonical URLs, not typed ids."""

    def test_lookup_sends_the_uri_not_the_typed_display_form(self) -> None:
        from logion_indexer.dedup import query_known_resources
        from logion_indexer.transport import FakeTransport, HttpResponse

        transport = FakeTransport()
        url = (
            "https://api.test/v1/admin/indexing/known?ids=gh%3Aoctocat%2Fhello"
        )
        transport.set_response(
            url,
            HttpResponse(
                200,
                json.dumps({
                    "known": {
                        "gh:octocat/hello": {
                            "kind": "indexed_listing",
                            "id": "abc",
                        }
                    }
                }).encode(),
            ),
        )
        known = query_known_resources(
            [CanonicalResourceId("plugin", "gh:octocat/hello")],
            transport,
            "https://api.test",
        )
        assert known["gh:octocat/hello"]["kind"] == "indexed_listing"

    def test_a_known_resource_updates_instead_of_recreating(self) -> None:
        """A typed key would make every run report the resource as new."""
        resource = _make_resource()
        known = {"gh:octocat/hello": {"kind": "indexed_listing", "id": "a"}}
        plan = build_resource_plan([resource], known)
        assert len(plan.update) == 1
        assert plan.create == []

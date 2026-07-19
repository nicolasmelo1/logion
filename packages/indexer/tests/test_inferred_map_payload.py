"""Tests for inferred_map/map_flags on every pushed item."""

from __future__ import annotations

from logion_indexer.canonical import CanonicalSkillId
from logion_indexer.models import DiscoveredSkill, DiscoveryChannel
from logion_indexer.pusher import serialize_item


def _make_skill_with_map(
    *,
    inferred_map: dict | None = None,
    map_flags: tuple[str, ...] = (),
    title: str = "frontmatter-title",
) -> DiscoveredSkill:
    return DiscoveredSkill(
        canonical=CanonicalSkillId(
            owner="octocat", repo="hello", subpath="skills/foo"
        ),
        title=title,
        summary="A test skill",
        original_author="octocat",
        license_spdx="MIT",
        source_commit="abc123",
        tags=("coding",),
        channels=(
            DiscoveryChannel(
                hub_slug="clawhub",
                hub_url="https://clawhub.ai/skills/foo",
                hub_verified=True,
            ),
        ),
        inferred_map=inferred_map,
        map_flags=map_flags,
    )


class TestInferredMapPayload:
    def test_inferred_map_on_every_item(self) -> None:
        inferred_map = {
            "version": 1,
            "package": {"slug": "foo-skill"},
            "components": {
                "capabilities": {
                    "foo-skill": {"entrypoint": "skills/foo/SKILL.md"}
                },
                "runtime": {
                    "include": ["skills/foo/**"],
                    "entrypoint": "skills/foo/SKILL.md",
                },
            },
        }
        skill = _make_skill_with_map(
            inferred_map=inferred_map,
            map_flags=("skillmap_frontmatter_missing",),
        )
        item = serialize_item(skill)
        assert item["inferred_map"] is not None
        assert item["inferred_map"]["version"] == 1
        assert item["inferred_map"]["package"]["slug"] == "foo-skill"

    def test_map_flags_on_every_item(self) -> None:
        skill = _make_skill_with_map(
            map_flags=("skillmap_frontmatter_missing", "no_license"),
        )
        item = serialize_item(skill)
        assert "skillmap_frontmatter_missing" in item["map_flags"]
        assert "no_license" in item["map_flags"]

    def test_null_inferred_map_allowed(self) -> None:
        skill = _make_skill_with_map(inferred_map=None)
        item = serialize_item(skill)
        assert item["inferred_map"] is None

    def test_frontmatter_title_preferred(self) -> None:
        """Frontmatter title should be preferred over hub title."""
        skill = _make_skill_with_map(title="frontmatter-title")
        item = serialize_item(skill)
        assert item["title"] == "frontmatter-title"

    def test_fragment_has_required_fields(self) -> None:
        """The inferred_map fragment must have version, package, components."""
        inferred_map = {
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
        skill = _make_skill_with_map(inferred_map=inferred_map)
        item = serialize_item(skill)
        assert "version" in item["inferred_map"]
        assert "package" in item["inferred_map"]
        assert "components" in item["inferred_map"]
        assert "capabilities" in item["inferred_map"]["components"]
        assert "runtime" in item["inferred_map"]["components"]

    def test_channels_serialized(self) -> None:
        skill = _make_skill_with_map()
        item = serialize_item(skill)
        assert len(item["channels"]) == 1
        ch = item["channels"][0]
        assert ch["hub_slug"] == "clawhub"
        assert ch["hub_verified"] is True

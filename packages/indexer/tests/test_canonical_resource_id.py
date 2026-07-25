# SPDX-License-Identifier: MIT
"""Tests for CanonicalResourceId and the generic resource model."""

from __future__ import annotations

import pytest

from logion_indexer.canonical import CanonicalResourceId, CanonicalSkillId


class TestCanonicalResourceIdCreation:
    def test_skill_type(self) -> None:
        rid = CanonicalResourceId(
            resource_type="skill", uri="gh:octocat/hello"
        )
        assert rid.resource_type == "skill"
        assert rid.uri == "gh:octocat/hello"
        assert str(rid) == "skill:gh:octocat/hello"

    def test_plugin_type(self) -> None:
        rid = CanonicalResourceId(
            resource_type="plugin", uri="npm:eslint-plugin-foo"
        )
        assert rid.resource_type == "plugin"
        assert str(rid) == "plugin:npm:eslint-plugin-foo"

    def test_mcp_server_type(self) -> None:
        rid = CanonicalResourceId(
            resource_type="mcp_server", uri="npm:@modelcontextprotocol/server"
        )
        assert rid.resource_type == "mcp_server"
        assert str(rid) == "mcp_server:npm:@modelcontextprotocol/server"

    def test_model_type(self) -> None:
        rid = CanonicalResourceId(
            resource_type="model", uri="hf:meta-llama/Llama-3"
        )
        assert rid.resource_type == "model"

    def test_course_type(self) -> None:
        rid = CanonicalResourceId(
            resource_type="course", uri="logion:course-123"
        )
        assert rid.resource_type == "course"

    def test_type_lowercased(self) -> None:
        rid = CanonicalResourceId(
            resource_type="Skill", uri="gh:octocat/hello"
        )
        assert rid.resource_type == "skill"

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid resource_type"):
            CanonicalResourceId(resource_type="invalid", uri="x:y")

    def test_ordering(self) -> None:
        a = CanonicalResourceId(resource_type="model", uri="hf:a/b")
        b = CanonicalResourceId(resource_type="skill", uri="gh:a/b")
        c = CanonicalResourceId(resource_type="skill", uri="gh:a/c")
        assert a < b
        assert b < c

    def test_equality_and_hash(self) -> None:
        a = CanonicalResourceId(resource_type="skill", uri="gh:octocat/hello")
        b = CanonicalResourceId(resource_type="skill", uri="gh:octocat/hello")
        assert a == b
        assert hash(a) == hash(b)
        assert len({a, b}) == 1


class TestCanonicalResourceIdFromStr:
    def test_parse_typed_prefix(self) -> None:
        rid = CanonicalResourceId.from_str("skill:gh:octocat/hello")
        assert rid.resource_type == "skill"
        assert rid.uri == "gh:octocat/hello"

    def test_parse_plugin_prefix(self) -> None:
        rid = CanonicalResourceId.from_str("plugin:npm:eslint-plugin-foo")
        assert rid.resource_type == "plugin"
        assert rid.uri == "npm:eslint-plugin-foo"

    def test_bare_gh_string_defaults_to_skill(self) -> None:
        rid = CanonicalResourceId.from_str("gh:octocat/hello")
        assert rid.resource_type == "skill"
        assert rid.uri == "gh:octocat/hello"

    def test_round_trip(self) -> None:
        original = "skill:gh:octocat/hello#skills/bar"
        rid = CanonicalResourceId.from_str(original)
        assert str(rid) == original


class TestFromSkillId:
    def test_lift_skill_id(self) -> None:
        skill_id = CanonicalSkillId(owner="octocat", repo="hello")
        rid = CanonicalResourceId.from_skill_id(skill_id)
        assert rid.resource_type == "skill"
        assert rid.uri == str(skill_id)
        assert rid.uri == "gh:octocat/hello"

    def test_lift_with_subpath(self) -> None:
        skill_id = CanonicalSkillId(
            owner="octocat", repo="hello", subpath="skills/bar"
        )
        rid = CanonicalResourceId.from_skill_id(skill_id)
        assert rid.resource_type == "skill"
        assert rid.uri == "gh:octocat/hello#skills/bar"

    def test_skill_round_trip_via_resource_id(self) -> None:
        skill_id = CanonicalSkillId(owner="anthropics", repo="skills")
        rid = CanonicalResourceId.from_skill_id(skill_id)
        # Recover skill_id via from_str on CanonicalSkillId
        recovered = CanonicalSkillId.from_str(rid.uri)
        assert recovered == skill_id

"""Tests for canonical skill id normalization, str round-trip, ordering."""

from __future__ import annotations

from logion_indexer.canonical import CanonicalSkillId


class TestNormalization:
    def test_basic_owner_repo(self) -> None:
        cid = CanonicalSkillId(owner="Octocat", repo="Hello-World")
        assert cid.owner == "octocat"
        assert cid.repo == "hello-world"
        assert cid.subpath == ""
        assert str(cid) == "gh:octocat/hello-world"

    def test_strip_dotgit(self) -> None:
        cid = CanonicalSkillId(owner="octocat", repo="repo.git")
        assert cid.repo == "repo"
        assert str(cid) == "gh:octocat/repo"

    def test_lowercase_owner_repo(self) -> None:
        cid = CanonicalSkillId(owner="AnThropicS", repo="Skills")
        assert cid.owner == "anthropics"
        assert cid.repo == "skills"

    def test_subpath_normalized(self) -> None:
        cid = CanonicalSkillId(
            owner="octocat", repo="hello", subpath="/skills/foo/"
        )
        assert cid.subpath == "skills/foo"
        assert str(cid) == "gh:octocat/hello#skills/foo"

    def test_subpath_lowercased(self) -> None:
        cid = CanonicalSkillId(
            owner="octocat", repo="hello", subpath="Skills/Foo"
        )
        assert cid.subpath == "skills/foo"

    def test_empty_subpath(self) -> None:
        cid = CanonicalSkillId(owner="o", repo="r", subpath="")
        assert cid.subpath == ""
        assert str(cid) == "gh:o/r"

    def test_dotgit_with_subpath(self) -> None:
        cid = CanonicalSkillId(
            owner="octocat", repo="repo.git", subpath="skills/bar"
        )
        assert cid.repo == "repo"
        assert str(cid) == "gh:octocat/repo#skills/bar"


class TestFromStr:
    def test_parse_gh_prefix(self) -> None:
        cid = CanonicalSkillId.from_str("gh:octocat/hello-world")
        assert cid.owner == "octocat"
        assert cid.repo == "hello-world"
        assert cid.subpath == ""

    def test_parse_with_subpath(self) -> None:
        cid = CanonicalSkillId.from_str("gh:octocat/hello-world#skills/foo")
        assert cid.owner == "octocat"
        assert cid.repo == "hello-world"
        assert cid.subpath == "skills/foo"

    def test_parse_raw_owner_repo(self) -> None:
        cid = CanonicalSkillId.from_str("Octocat/Hello-World")
        assert cid.owner == "octocat"
        assert cid.repo == "hello-world"

    def test_parse_github_url(self) -> None:
        cid = CanonicalSkillId.from_str(
            "https://github.com/octocat/hello-world"
        )
        assert cid.owner == "octocat"
        assert cid.repo == "hello-world"

    def test_parse_github_url_with_dotgit(self) -> None:
        cid = CanonicalSkillId.from_str(
            "https://github.com/octocat/hello-world.git"
        )
        assert cid.owner == "octocat"
        assert cid.repo == "hello-world"

    def test_round_trip(self) -> None:
        original = "gh:anthropics/skills#my-skill"
        cid = CanonicalSkillId.from_str(original)
        assert str(cid) == original

    def test_round_trip_no_subpath(self) -> None:
        original = "gh:anthropics/skills"
        cid = CanonicalSkillId.from_str(original)
        assert str(cid) == original

    def test_invalid_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="invalid canonical id"):
            CanonicalSkillId.from_str("just-a-name")


class TestFromGithubUrl:
    def test_https_url(self) -> None:
        cid = CanonicalSkillId.from_github_url(
            "https://github.com/octocat/hello-world"
        )
        assert cid.owner == "octocat"
        assert cid.repo == "hello-world"

    def test_https_url_with_subpath(self) -> None:
        cid = CanonicalSkillId.from_github_url(
            "https://github.com/octocat/hello-world/tree/main/skills/foo"
        )
        assert cid.owner == "octocat"
        assert cid.repo == "hello-world"
        assert cid.subpath == "tree/main/skills/foo"

    def test_dotgit_url(self) -> None:
        cid = CanonicalSkillId.from_github_url(
            "https://github.com/octocat/hello-world.git"
        )
        assert cid.repo == "hello-world"


class TestOrdering:
    def test_order_by_owner_repo(self) -> None:
        a = CanonicalSkillId(owner="aaa", repo="repo")
        b = CanonicalSkillId(owner="bbb", repo="repo")
        assert a < b

    def test_order_same_owner(self) -> None:
        a = CanonicalSkillId(owner="aaa", repo="aaa")
        b = CanonicalSkillId(owner="aaa", repo="bbb")
        assert a < b

    def test_order_with_subpath(self) -> None:
        a = CanonicalSkillId(owner="aaa", repo="repo", subpath="a")
        b = CanonicalSkillId(owner="aaa", repo="repo", subpath="b")
        assert a < b

    def test_sort_list(self) -> None:
        ids = [
            CanonicalSkillId(owner="zzz", repo="repo"),
            CanonicalSkillId(owner="aaa", repo="repo"),
            CanonicalSkillId(owner="mmm", repo="repo"),
        ]
        sorted_ids = sorted(ids)
        assert sorted_ids[0].owner == "aaa"
        assert sorted_ids[-1].owner == "zzz"

    def test_equality_and_hash(self) -> None:
        a = CanonicalSkillId(owner="octocat", repo="hello")
        b = CanonicalSkillId(owner="Octocat", repo="Hello")
        assert a == b
        assert hash(a) == hash(b)
        assert len({a, b}) == 1

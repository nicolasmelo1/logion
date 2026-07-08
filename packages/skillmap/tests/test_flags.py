"""Repo-level needs_review flags and emission (includes, runtime)."""

from __future__ import annotations

from _treeutil import blob_store, codes, make_tree

from logion_skillmap.constants import MAX_COMPONENT_CAPABILITIES
from logion_skillmap.inference import infer


def _skill(name: str) -> bytes:
    return f"---\nname: {name}\ndescription: d\n---\nBody.".encode()


class TestNoLicense:
    def test_missing_license_flagged(self):
        tree = make_tree([("skills/a/SKILL.md", "blob", 30)])
        result = infer(tree, blob_store({"skills/a/SKILL.md": _skill("a")}))
        assert "no_license" in codes(result)

    def test_license_present_no_flag(self):
        tree = make_tree([
            ("LICENSE", "blob", 100),
            ("skills/a/SKILL.md", "blob", 30),
        ])
        blobs = {"LICENSE": b"MIT", "skills/a/SKILL.md": _skill("a")}
        result = infer(tree, blob_store(blobs))
        assert "no_license" not in codes(result)


class TestHiddenTreeOnly:
    def test_all_hidden_roots_flagged(self):
        tree = make_tree([
            ("LICENSE", "blob", 10),
            (".agents/skills/a/SKILL.md", "blob", 30),
        ])
        blobs = {"LICENSE": b"MIT", ".agents/skills/a/SKILL.md": _skill("a")}
        result = infer(tree, blob_store(blobs))
        assert "hidden_tree_only" in codes(result)

    def test_visible_root_not_flagged(self):
        tree = make_tree([("skills/a/SKILL.md", "blob", 30)])
        result = infer(tree, blob_store({"skills/a/SKILL.md": _skill("a")}))
        assert "hidden_tree_only" not in codes(result)


class TestAmbiguousPrimaryTree:
    def test_two_disjoint_trees_flagged(self):
        tree = make_tree([
            ("skills/a/SKILL.md", "blob", 30),
            ("plugins/p/skills/b/SKILL.md", "blob", 30),
        ])
        blobs = {
            "skills/a/SKILL.md": _skill("a"),
            "plugins/p/skills/b/SKILL.md": _skill("b"),
        }
        result = infer(tree, blob_store(blobs))
        assert "ambiguous_primary_tree" in codes(result)

    def test_single_tree_not_flagged(self):
        tree = make_tree([
            ("skills/a/SKILL.md", "blob", 30),
            ("skills/b/SKILL.md", "blob", 30),
        ])
        blobs = {
            "skills/a/SKILL.md": _skill("a"),
            "skills/b/SKILL.md": _skill("b"),
        }
        result = infer(tree, blob_store(blobs))
        assert "ambiguous_primary_tree" not in codes(result)


class TestComponentCap:
    def test_cap_exceeded_flagged(self):
        n = MAX_COMPONENT_CAPABILITIES + 1
        entries = [(f"skills/s{i}/SKILL.md", "blob", 30) for i in range(n)]
        blobs = {f"skills/s{i}/SKILL.md": _skill(f"s{i}") for i in range(n)}
        result = infer(make_tree(entries), blob_store(blobs))
        assert len(result.components) == n
        assert "skillmap_component_cap_exceeded" in codes(result)

    def test_under_cap_not_flagged(self):
        tree = make_tree([("skills/a/SKILL.md", "blob", 30)])
        result = infer(tree, blob_store({"skills/a/SKILL.md": _skill("a")}))
        assert "skillmap_component_cap_exceeded" not in codes(result)


class TestEmission:
    def test_capability_include_and_runtime_entrypoint(self):
        tree = make_tree([("skills/a/SKILL.md", "blob", 30)])
        result = infer(tree, blob_store({"skills/a/SKILL.md": _skill("a")}))
        pm = result.package_map
        assert pm.capabilities[0].include == ("skills/a/**",)
        assert pm.runtime is not None
        assert pm.runtime.entrypoint == "skills/a/SKILL.md"

    def test_repo_root_component_include(self):
        tree = make_tree([("SKILL.md", "blob", 30)])
        result = infer(tree, blob_store({"SKILL.md": _skill("skill")}))
        # A repo-root SKILL.md → single component rooted at repo root.
        assert result.components[0].root == ""
        assert result.package_map.capabilities[0].include == ("**",)

    def test_slug_override(self):
        tree = make_tree([("skills/a/SKILL.md", "blob", 30)])
        result = infer(
            tree, blob_store({"skills/a/SKILL.md": _skill("a")}), slug="custom"
        )
        assert result.package_map.slug == "custom"

"""Frontmatter metadata, spec conformance, and logion-file-in-skill."""

from __future__ import annotations

from _treeutil import blob_store, codes, make_tree

from logion_skillmap.inference import infer


class TestMetadata:
    def test_name_and_description_from_frontmatter(self):
        tree = make_tree([("skills/my-skill/SKILL.md", "blob", 40)])
        blobs = {
            "skills/my-skill/SKILL.md": (
                b"---\nname: my-skill\ndescription: A cool skill\n---\nBody."
            ),
        }
        result = infer(tree, blob_store(blobs))
        assert result.components[0].name == "my-skill"
        assert result.components[0].summary == "A cool skill"

    def test_name_fallback_to_dir_slug(self):
        tree = make_tree([("skills/my-skill/SKILL.md", "blob", 30)])
        blobs = {"skills/my-skill/SKILL.md": b"No frontmatter here."}
        result = infer(tree, blob_store(blobs))
        assert result.components[0].name == "my-skill"

    def test_missing_frontmatter_flagged(self):
        tree = make_tree([("skills/my-skill/SKILL.md", "blob", 30)])
        blobs = {"skills/my-skill/SKILL.md": b"No frontmatter here."}
        result = infer(tree, blob_store(blobs))
        assert "skillmap_frontmatter_missing" in codes(result)


class TestSpecConformance:
    def test_name_mismatch_flags(self):
        tree = make_tree([("skills/wrong-name/SKILL.md", "blob", 40)])
        blobs = {
            "skills/wrong-name/SKILL.md": (
                b"---\nname: different-name\ndescription: d\n---\n"
            ),
        }
        result = infer(tree, blob_store(blobs))
        assert "spec_nonconformant:name_mismatch" in codes(result)

    def test_missing_description_flags(self):
        tree = make_tree([("skills/my-skill/SKILL.md", "blob", 30)])
        blobs = {"skills/my-skill/SKILL.md": b"---\nname: my-skill\n---\n"}
        result = infer(tree, blob_store(blobs))
        assert "spec_nonconformant:description_length" in codes(result)

    def test_valid_frontmatter_no_spec_flags(self):
        tree = make_tree([("skills/my-skill/SKILL.md", "blob", 40)])
        blobs = {
            "skills/my-skill/SKILL.md": (
                b"---\nname: my-skill\ndescription: Ok\n---\n"
            ),
        }
        result = infer(tree, blob_store(blobs))
        spec_flags = [
            c for c in codes(result) if c.startswith("spec_nonconformant")
        ]
        assert spec_flags == []


class TestLogionFileInsideSkill:
    def test_logion_file_inside_skill_flagged(self):
        tree = make_tree([
            ("skills/my-skill/SKILL.md", "blob", 30),
            ("skills/my-skill/logion-package-map.yaml", "blob", 20),
        ])
        skill = b"---\nname: my-skill\ndescription: d\n---\n"
        blobs = {
            "skills/my-skill/SKILL.md": skill,
            "skills/my-skill/logion-package-map.yaml": b"version: 1\n",
        }
        result = infer(tree, blob_store(blobs))
        assert "skillmap_logion_file_inside_skill" in codes(result)

    def test_logion_file_inside_mirror_skill_flagged(self):
        skill_content = b"---\nname: my-skill\ndescription: d\n---\nContent."
        tree = make_tree([
            ("skills/my-skill/SKILL.md", "blob", 40),
            (".claude/skills/my-skill/SKILL.md", "blob", 40),
            (".claude/skills/my-skill/logion-package-map.yaml", "blob", 20),
        ])
        blobs = {
            "skills/my-skill/SKILL.md": skill_content,
            ".claude/skills/my-skill/SKILL.md": skill_content,
            ".claude/skills/my-skill/logion-package-map.yaml": b"version: 1\n",
        }
        result = infer(tree, blob_store(blobs))
        flags = [
            f
            for f in result.needs_review
            if f.code == "skillmap_logion_file_inside_skill"
        ]
        assert any(
            ".claude/skills/my-skill/logion-package-map.yaml" in f.path
            for f in flags
        )

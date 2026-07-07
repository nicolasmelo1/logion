"""Harness-mirror dedup: hash-grouping and canonical-choice ordering."""

from __future__ import annotations

from _treeutil import blob_store, make_tree

from logion_skillmap.inference import infer


class TestMirrorDedup:
    def test_dedup_by_content(self):
        skill_content = b"---\nname: myskill\ndescription: d\n---\nBody."
        tree = make_tree([
            ("skills/myskill/SKILL.md", "blob", 40),
            (".claude/skills/myskill/SKILL.md", "blob", 40),
        ])
        blobs = {
            "skills/myskill/SKILL.md": skill_content,
            ".claude/skills/myskill/SKILL.md": skill_content,
        }
        result = infer(tree, blob_store(blobs))
        assert len(result.components) == 1
        comp = result.components[0]
        # Non-hidden path wins as canonical.
        assert comp.root == "skills/myskill"
        assert ".claude/skills/myskill" in comp.mirrors

    def test_shortest_then_lexicographic(self):
        content = b"---\nname: x\ndescription: d\n---\nSame."
        tree = make_tree([
            ("a/b/x/SKILL.md", "blob", 30),
            ("z/x/SKILL.md", "blob", 30),
            ("m/x/SKILL.md", "blob", 30),
        ])
        blobs = dict.fromkeys(
            ["a/b/x/SKILL.md", "z/x/SKILL.md", "m/x/SKILL.md"], content
        )
        result = infer(tree, blob_store(blobs))
        assert len(result.components) == 1
        # Shortest wins ("m/x"/"z/x" beat "a/b/x"); "m/x" < "z/x" lexically.
        assert result.components[0].root == "m/x"

    def test_different_content_both_kept(self):
        tree = make_tree([
            ("skills/a/SKILL.md", "blob", 20),
            ("skills/b/SKILL.md", "blob", 20),
        ])
        blobs = {
            "skills/a/SKILL.md": b"---\nname: a\ndescription: d\n---\nA",
            "skills/b/SKILL.md": b"---\nname: b\ndescription: d\n---\nB",
        }
        result = infer(tree, blob_store(blobs))
        assert len(result.components) == 2

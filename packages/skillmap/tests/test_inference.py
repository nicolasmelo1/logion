"""Tests for the deterministic inference engine."""

from __future__ import annotations

import json

import pytest

from logion_skillmap.inference import infer
from logion_skillmap.models import TreeEntry

# Helpers


def _make_tree(entries: list[tuple[str, str, int | None]]) -> list[TreeEntry]:
    """Build a list of TreeEntry from (path, type, size) tuples."""
    return [TreeEntry(path=p, type=t, size=s) for p, t, s in entries]


def _blob_store(files: dict[str, bytes]) -> callable:
    """Create a read_blob callback from a dict of path→bytes."""

    def read_blob(path: str) -> bytes:
        return files.get(path, b"")

    return read_blob


class TestPrecedence:
    def test_author_map_wins(self):
        tree = _make_tree([
            ("logion-package-map.yaml", "blob", 50),
            (".claude-plugin/plugin.json", "blob", 40),
            ("skills/cool/SKILL.md", "blob", 30),
        ])
        blobs = {
            "logion-package-map.yaml": b"""\
version: 1
slug: author-pkg
capabilities:
  - name: authored
    entrypoint: skills/cool/main.py
""",
            ".claude-plugin/plugin.json": json.dumps({
                "skills": [{"path": "skills/cool"}]
            }).encode(),
            "skills/cool/SKILL.md": b"---\nname: cool\n---\nCool skill.",
        }
        result = infer(tree, _blob_store(blobs))
        assert result.source == "author_map"
        assert result.package_map.slug == "author-pkg"
        assert result.components[0].name == "authored"

    def test_plugin_manifest_wins_over_scan(self):
        tree = _make_tree([
            (".claude-plugin/plugin.json", "blob", 40),
            ("skills/cool/SKILL.md", "blob", 30),
        ])
        blobs = {
            ".claude-plugin/plugin.json": json.dumps({
                "skills": [{"path": "skills/cool"}]
            }).encode(),
            "skills/cool/SKILL.md": b"---\nname: cool\n---\nCool skill.",
        }
        result = infer(tree, _blob_store(blobs))
        assert result.source == "plugin_manifest"

    def test_skill_scan_fallback(self):
        tree = _make_tree([
            ("skills/cool/SKILL.md", "blob", 30),
        ])
        blobs = {
            "skills/cool/SKILL.md": b"---\nname: cool\n---\nCool skill.",
        }
        result = infer(tree, _blob_store(blobs))
        assert result.source == "skill_scan"


# Exclusion


class TestExclusion:
    @pytest.mark.parametrize(
        "excluded_dir",
        [
            "test",
            "tests",
            "fixtures",
            "fixture",
            "deprecated",
            "node_modules",
            ".git",
            ".github",
        ],
    )
    def test_excluded_directories_dropped(self, excluded_dir):
        tree = _make_tree([
            (f"{excluded_dir}/myskill/SKILL.md", "blob", 20),
        ])
        blobs = {
            f"{excluded_dir}/myskill/SKILL.md": b"---\nname: myskill\n---\n",
        }
        result = infer(tree, _blob_store(blobs))
        assert len(result.components) == 0


# Harness-mirror dedup


class TestMirrorDedup:
    def test_dedup_by_content(self):
        skill_content = b"---\nname: myskill\n---\nSkill content."
        tree = _make_tree([
            ("skills/myskill/SKILL.md", "blob", 30),
            (".claude/skills/myskill/SKILL.md", "blob", 30),
        ])
        blobs = {
            "skills/myskill/SKILL.md": skill_content,
            ".claude/skills/myskill/SKILL.md": skill_content,
        }
        result = infer(tree, _blob_store(blobs))
        # Only one canonical component
        assert len(result.components) == 1
        # Non-hidden path wins
        comp = result.components[0]
        assert comp.root == "skills/myskill"
        # The hidden path is a mirror
        assert ".claude/skills/myskill" in comp.mirrors

    def test_different_content_both_kept(self):
        tree = _make_tree([
            ("skills/a/SKILL.md", "blob", 20),
            ("skills/b/SKILL.md", "blob", 20),
        ])
        blobs = {
            "skills/a/SKILL.md": b"---\nname: a\n---\nA",
            "skills/b/SKILL.md": b"---\nname: b\n---\nB",
        }
        result = infer(tree, _blob_store(blobs))
        assert len(result.components) == 2


# Metadata parsing


class TestMetadata:
    def test_name_from_frontmatter(self):
        tree = _make_tree([
            ("skills/my-skill/SKILL.md", "blob", 30),
        ])
        blobs = {
            "skills/my-skill/SKILL.md": (
                b"---\nname: my-skill\ndescription: A cool skill\n---\nBody."
            ),
        }
        result = infer(tree, _blob_store(blobs))
        assert result.components[0].name == "my-skill"
        assert result.components[0].summary == "A cool skill"

    def test_name_fallback_to_dir_slug(self):
        tree = _make_tree([
            ("skills/my-skill/SKILL.md", "blob", 30),
        ])
        blobs = {
            "skills/my-skill/SKILL.md": b"No frontmatter here.",
        }
        result = infer(tree, _blob_store(blobs))
        # Fallback: directory slug
        assert result.components[0].name == "my-skill"


# Spec conformance flags


class TestSpecConformance:
    def test_name_mismatch_flags(self):
        tree = _make_tree([
            ("skills/wrong-name/SKILL.md", "blob", 30),
        ])
        blobs = {
            "skills/wrong-name/SKILL.md": b"---\nname: different-name\n---\n",
        }
        result = infer(tree, _blob_store(blobs))
        flags = [
            f
            for f in result.needs_review
            if f.code == "spec_nonconformant:name_mismatch"
        ]
        assert len(flags) > 0

    def test_valid_name_no_flags(self):
        tree = _make_tree([
            ("skills/my-skill/SKILL.md", "blob", 30),
        ])
        blobs = {
            "skills/my-skill/SKILL.md": (
                b"---\nname: my-skill\ndescription: Ok\n---\n"
            ),
        }
        result = infer(tree, _blob_store(blobs))
        spec_flags = [
            f
            for f in result.needs_review
            if f.code.startswith("spec_nonconformant")
        ]
        assert len(spec_flags) == 0


# Determinism


class TestDeterminism:
    def test_double_run_equality(self):
        tree = _make_tree([
            ("skills/alpha/SKILL.md", "blob", 30),
            ("skills/beta/SKILL.md", "blob", 30),
        ])
        blobs = {
            "skills/alpha/SKILL.md": b"---\nname: alpha\n---\nAlpha.",
            "skills/beta/SKILL.md": b"---\nname: beta\n---\nBeta.",
        }
        result1 = infer(tree, _blob_store(blobs))
        result2 = infer(tree, _blob_store(blobs))
        assert result1 == result2


# Logion file inside skill directory


class TestLogionFileInsideSkill:
    def test_logion_file_inside_skill_flagged(self):
        tree = _make_tree([
            ("skills/my-skill/SKILL.md", "blob", 30),
            ("skills/my-skill/logion-package-map.yaml", "blob", 20),
        ])
        blobs = {
            "skills/my-skill/SKILL.md": b"---\nname: my-skill\n---\n",
            "skills/my-skill/logion-package-map.yaml": b"version: 1\n",
        }
        # Since logion-package-map.yaml is NOT at root, we get skill_scan
        result = infer(tree, _blob_store(blobs))
        flags = [
            f
            for f in result.needs_review
            if f.code == "skillmap_logion_file_inside_skill"
        ]
        assert len(flags) > 0

    def test_logion_file_inside_mirror_skill_flagged(self):
        """Logion files inside mirror skill dirs are flagged."""
        skill_content = b"---\nname: my-skill\n---\nSkill content."
        tree = _make_tree([
            ("skills/my-skill/SKILL.md", "blob", 30),
            (".claude/skills/my-skill/SKILL.md", "blob", 30),
            (".claude/skills/my-skill/logion-package-map.yaml", "blob", 20),
        ])
        blobs = {
            "skills/my-skill/SKILL.md": skill_content,
            ".claude/skills/my-skill/SKILL.md": skill_content,
            ".claude/skills/my-skill/logion-package-map.yaml": b"version: 1\n",
        }
        result = infer(tree, _blob_store(blobs))
        flags = [
            f
            for f in result.needs_review
            if f.code == "skillmap_logion_file_inside_skill"
        ]
        assert len(flags) > 0
        # The flag should reference the mirror path
        assert any(
            ".claude/skills/my-skill/logion-package-map.yaml" in f.path
            for f in flags
        )

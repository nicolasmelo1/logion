"""Precedence: author map > plugin manifest > SKILL.md scan."""

from __future__ import annotations

import json

from _treeutil import blob_store, make_tree

from logion_skillmap.inference import infer

_AUTHOR_MAP = b"""\
version: 1
package:
  slug: author-pkg
components:
  capabilities:
    authored:
      entrypoint: skills/cool/SKILL.md
"""


class TestPrecedence:
    def test_author_map_wins(self):
        tree = make_tree([
            ("logion-package-map.yaml", "blob", 80),
            (".claude-plugin/plugin.json", "blob", 40),
            ("skills/cool/SKILL.md", "blob", 30),
        ])
        blobs = {
            "logion-package-map.yaml": _AUTHOR_MAP,
            ".claude-plugin/plugin.json": json.dumps({
                "skills": [{"path": "skills/cool"}]
            }).encode(),
            "skills/cool/SKILL.md": b"---\nname: cool\n---\nCool skill.",
        }
        result = infer(tree, blob_store(blobs))
        assert result.source == "author_map"
        assert result.package_map.slug == "author-pkg"
        assert result.components[0].name == "authored"

    def test_plugin_manifest_wins_over_scan(self):
        tree = make_tree([
            (".claude-plugin/plugin.json", "blob", 40),
            ("skills/cool/SKILL.md", "blob", 30),
        ])
        blobs = {
            ".claude-plugin/plugin.json": json.dumps({
                "skills": [{"path": "skills/cool"}]
            }).encode(),
            "skills/cool/SKILL.md": b"---\nname: cool\n---\nCool skill.",
        }
        result = infer(tree, blob_store(blobs))
        assert result.source == "plugin_manifest"

    def test_skill_scan_fallback(self):
        tree = make_tree([("skills/cool/SKILL.md", "blob", 30)])
        blobs = {"skills/cool/SKILL.md": b"---\nname: cool\n---\nCool skill."}
        result = infer(tree, blob_store(blobs))
        assert result.source == "skill_scan"

    def test_manifest_missing_path_flagged(self):
        tree = make_tree([
            (".claude-plugin/plugin.json", "blob", 40),
            ("skills/real/SKILL.md", "blob", 30),
        ])
        blobs = {
            ".claude-plugin/plugin.json": json.dumps({
                "skills": [
                    {"path": "skills/real"},
                    {"path": "skills/deleted"},
                ]
            }).encode(),
            "skills/real/SKILL.md": b"---\nname: real\n---\nReal.",
        }
        result = infer(tree, blob_store(blobs))
        assert result.source == "plugin_manifest"
        missing = [
            f for f in result.needs_review if f.code == "manifest_path_missing"
        ]
        assert len(missing) == 1
        assert missing[0].path == "skills/deleted"

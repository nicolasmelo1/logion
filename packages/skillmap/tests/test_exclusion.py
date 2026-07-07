"""Exclusion pass: excluded path segments drop candidates (and flag)."""

from __future__ import annotations

import pytest
from _treeutil import blob_store, codes, make_tree

from logion_skillmap.inference import infer


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
        tree = make_tree([
            (f"{excluded_dir}/myskill/SKILL.md", "blob", 20),
        ])
        blobs = {
            f"{excluded_dir}/myskill/SKILL.md": b"---\nname: myskill\n---\n",
        }
        result = infer(tree, blob_store(blobs))
        assert len(result.components) == 0
        assert "skillmap_excluded_segment" in codes(result)

    def test_non_excluded_kept(self):
        tree = make_tree([("skills/keep/SKILL.md", "blob", 20)])
        blobs = {
            "skills/keep/SKILL.md": b"---\nname: keep\ndescription: d\n---\n"
        }
        result = infer(tree, blob_store(blobs))
        assert len(result.components) == 1
        assert "skillmap_excluded_segment" not in codes(result)

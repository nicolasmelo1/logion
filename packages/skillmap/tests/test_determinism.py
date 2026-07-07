"""Determinism: same tree + blobs → identical InferenceResult."""

from __future__ import annotations

import json

from _treeutil import blob_store, make_tree

from logion_skillmap.inference import infer


def _fm(name: str) -> bytes:
    return f"---\nname: {name}\ndescription: d\n---\nBody.".encode()


def _rich_tree():
    tree = make_tree([
        ("LICENSE", "blob", 100),
        (".claude-plugin/plugin.json", "blob", 60),
        ("skills/alpha/SKILL.md", "blob", 40),
        ("skills/beta/SKILL.md", "blob", 40),
        (".claude/skills/alpha/SKILL.md", "blob", 40),
    ])
    alpha = b"---\nname: alpha\ndescription: A\n---\nAlpha."
    blobs = {
        ".claude-plugin/plugin.json": json.dumps({
            "skills": [{"path": "skills/alpha"}, {"path": "skills/beta"}]
        }).encode(),
        "skills/alpha/SKILL.md": alpha,
        "skills/beta/SKILL.md": b"---\nname: beta\ndescription: B\n---\nBeta.",
        ".claude/skills/alpha/SKILL.md": alpha,
    }
    return tree, blobs


class TestDeterminism:
    def test_double_run_equality_scan(self):
        tree = make_tree([
            ("skills/alpha/SKILL.md", "blob", 40),
            ("skills/beta/SKILL.md", "blob", 40),
        ])
        blobs = {
            "skills/alpha/SKILL.md": _fm("alpha"),
            "skills/beta/SKILL.md": _fm("beta"),
        }
        assert infer(tree, blob_store(blobs)) == infer(tree, blob_store(blobs))

    def test_double_run_equality_rich(self):
        tree, blobs = _rich_tree()
        assert infer(tree, blob_store(blobs)) == infer(tree, blob_store(blobs))

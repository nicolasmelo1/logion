"""Tests for content queue."""

from __future__ import annotations

from pathlib import Path

from social_management.content.queue import add, list_drafts
from social_management.core.models import PostDraft


def test_add_writes_yaml(tmp_content_dir: Path) -> None:
    draft = PostDraft(platform="x", target="x", text="hello world")
    path = add(draft, content_dir=tmp_content_dir)
    assert path.exists()
    assert path.name == "x-000.yaml"
    drafts = list_drafts(content_dir=tmp_content_dir)
    assert len(drafts) == 1
    assert drafts[0].platform == "x"
    assert drafts[0].text == "hello world"
    assert drafts[0].source_file == str(path)


def test_list_drafts_sorted(tmp_content_dir: Path) -> None:
    d1 = PostDraft(platform="x", target="x", text="first")
    d2 = PostDraft(platform="discord", target="general", text="second")
    add(d1, content_dir=tmp_content_dir)
    add(d2, content_dir=tmp_content_dir)
    drafts = list_drafts(content_dir=tmp_content_dir)
    assert len(drafts) == 2
    # sorted() on filenames: discord-001.yaml < x-000.yaml (d < x).
    assert drafts[0].platform == "discord"
    assert drafts[1].platform == "x"

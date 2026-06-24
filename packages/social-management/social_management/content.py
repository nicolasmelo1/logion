"""Local content queue: YAML drafts under content/ the operator approves."""

from __future__ import annotations

from pathlib import Path

import yaml

from social_management.models import PostDraft

CONTENT_DIR = Path("content")


def add(draft: PostDraft, *, content_dir: Path = CONTENT_DIR) -> Path:
    """Write a draft to content/<platform>-<n>.yaml and return its path."""
    content_dir.mkdir(parents=True, exist_ok=True)
    existing = list(content_dir.glob("*.yaml"))
    n = len(existing)
    filename = f"{draft.platform}-{n:03d}.yaml"
    path = content_dir / filename
    payload = {
        "platform": draft.platform,
        "target": draft.target,
        "text": draft.text,
        "has_link": draft.has_link,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path


def list_drafts(*, content_dir: Path = CONTENT_DIR) -> list[PostDraft]:
    """Load every *.yaml in content/ into PostDraft objects (sorted)."""
    drafts: list[PostDraft] = []
    for path in sorted(content_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        draft = PostDraft(**data)
        draft.source_file = str(path)
        drafts.append(draft)
    return drafts

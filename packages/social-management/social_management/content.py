"""Local content queue: YAML drafts under content/ the operator approves."""

from __future__ import annotations

from pathlib import Path

import yaml

from social_management.models import PostDraft

CONTENT_DIR = Path("content")


def add(
    draft: PostDraft,
    *,
    content_dir: Path = CONTENT_DIR,
    dry_run: bool = False,
) -> Path:
    """Write a draft to content/<platform>-<n>.yaml and return its path.

    Uses max-index+1 so deleted drafts don't cause index reuse and
    overwrite an existing file. If dry_run, return the would-be path
    without writing or creating directories.
    """
    if dry_run:
        existing = list(content_dir.glob(f"{draft.platform}-*.yaml"))
        max_n = _max_index(existing, draft.platform)
        return content_dir / f"{draft.platform}-{max_n + 1:03d}.yaml"
    content_dir.mkdir(parents=True, exist_ok=True)
    existing = list(content_dir.glob(f"{draft.platform}-*.yaml"))
    max_n = _max_index(existing, draft.platform)
    filename = f"{draft.platform}-{max_n + 1:03d}.yaml"
    path = content_dir / filename
    payload = {
        "platform": draft.platform,
        "target": draft.target,
        "text": draft.text,
        "has_link": draft.has_link,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path


def _max_index(existing: list[Path], platform: str) -> int:
    """Extract the highest numeric suffix from existing files."""
    prefix = f"{platform}-"
    max_n = -1
    for p in existing:
        stem = p.stem  # e.g. "x-002"
        if stem.startswith(prefix):
            suffix = stem[len(prefix) :]
            try:
                max_n = max(max_n, int(suffix))
            except ValueError:
                continue
    return max_n


def list_drafts(*, content_dir: Path = CONTENT_DIR) -> list[PostDraft]:
    """Load every *.yaml in content/ into PostDraft objects (sorted)."""
    drafts: list[PostDraft] = []
    for path in sorted(content_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        draft = PostDraft(**data)
        draft.source_file = str(path)
        drafts.append(draft)
    return drafts

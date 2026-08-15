#!/usr/bin/env python3
"""Prepare isolated harness-scope fixtures and emit public paths as JSON."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _write_skill(skills_dir: Path, name: str, marker: str) -> None:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: Fixture from {marker}\n"
        "---\n\n"
        f"# {name}\n\nFixture from {marker}.\n",
        encoding="utf-8",
    )


def _snapshot(roots: list[Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    # Git internals churn on their own (index mtimes, refs); the snapshot
    # is about installed content, not repository plumbing.
    skip_dirs = {
        ".cache",
        "__pycache__",
        ".local",
        "Library",
        ".git",
        ".npm",
        ".bun",
        ".yarn",
        "node_modules",
    }
    skip_files = {
        ".bashrc",
        ".bash_profile",
        ".bash_history",
        ".zshrc",
        ".zsh_history",
        ".profile",
        ".npmrc",
    }
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                if any(part in skip_dirs for part in path.parts):
                    continue
                if path.parent == root and path.name in skip_files:
                    continue
                result[str(path.resolve())] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    return result


def _init_repo(root: Path) -> None:
    """Create a real Git worktree the native managers will accept.

    A bare ``.git`` directory is enough for Logion's own scope resolution
    but not for `npx skills`, which shells out to Git. The fixture has to
    be a real repository or the delegated-acquisition phase proves nothing.
    """
    root.mkdir(parents=True, exist_ok=True)
    if (root / ".git").is_dir():
        return
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main", str(root)],
        check=True,
        capture_output=True,
    )
    for key, value in (
        ("user.email", "fixture@logion.test"),
        ("user.name", "Logion Fixture"),
    ):
        subprocess.run(
            ["git", "-C", str(root), "config", key, value],
            check=True,
            capture_output=True,
        )


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: setup_harness_scope_fixture.py WORKSPACE")
    workspace = Path(sys.argv[1]).resolve()
    fixture_root = workspace / "xpto"
    # A second repository proves an install in one repository creates
    # nothing in another.
    other_repo = workspace / "acme"
    nested_cwd = fixture_root / "nested"
    isolated_home = workspace / "home"
    outputs = workspace / "evidence"
    nested_cwd.mkdir(parents=True, exist_ok=True)
    isolated_home.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    _init_repo(fixture_root)
    _init_repo(other_repo)

    fixtures = {
        nested_cwd / ".agents" / "skills": "repo-current-agents",
        nested_cwd / ".claude" / "skills": "repo-current-claude",
        nested_cwd / ".pi" / "skills": "repo-current-pi",
        fixture_root / ".agents" / "skills": "repo-root-agents",
        fixture_root / ".claude" / "skills": "repo-root-claude",
        fixture_root / ".pi" / "skills": "repo-root-pi",
        isolated_home / ".agents" / "skills": "user-agents",
        isolated_home / ".codex" / "skills": "user-codex-legacy",
        isolated_home / ".claude" / "skills": "user-claude",
        isolated_home / ".hermes" / "skills": "user-hermes",
        isolated_home / ".pi" / "agent" / "skills": "user-pi",
    }
    for path, marker in fixtures.items():
        _write_skill(path, "acme", marker)

    snapshot_path = outputs / "before.json"
    snapshot_path.write_text(
        json.dumps(
            _snapshot([fixture_root, other_repo, isolated_home]),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(  # noqa: T201
        json.dumps({
            "fixture_root": str(fixture_root),
            "other_repo_root": str(other_repo),
            "nested_cwd": str(nested_cwd),
            "isolated_home": str(isolated_home),
            "evidence_dir": str(outputs),
            "snapshot_path": str(snapshot_path),
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

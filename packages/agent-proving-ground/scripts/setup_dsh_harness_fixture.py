#!/usr/bin/env python3
"""Prepare an isolated DSH harness environment and emit paths as JSON.

Creates a Git repository for the developer, an isolated HOME, an evidence
directory, and a pre-existing native DSH profile (for the reconcile phase).
The snapshot captures the state before any Logion acquisition runs.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _init_repo(root: Path) -> None:
    """Create a real Git repository the DSH adapter will accept."""
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


def _write_dsh_profile(repo_root: Path, profile: str) -> None:
    """Create a pre-existing native DSH profile for the reconcile phase.

    The profile has a plugin installed directly via DSH (not through Logion)
    so the reconcile phase can recognize it without reinstalling.
    """
    profile_dir = repo_root / ".dsh" / "profiles" / profile
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Minimal package.json with one dependency
    (profile_dir / "package.json").write_text(
        json.dumps(
            {
                "name": f"dsh-profile-{profile}",
                "version": "1.0.0",
                "dependencies": {
                    "logion-fixtures/helper-b": "0.1.0",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # dsh.profile with bundles list referencing the pre-existing plugin
    (profile_dir / "dsh.profile").write_text(
        json.dumps(
            {
                "dsh": {
                    "profile": {
                        "bundles": ["logion-fixtures/helper-b"],
                    },
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _snapshot(roots: list[Path]) -> dict[str, str]:
    result: dict[str, str] = {}
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


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: setup_dsh_harness_fixture.py WORKSPACE")
    workspace = Path(sys.argv[1]).resolve()
    fixture_root = workspace / "dsh-repo"
    isolated_home = workspace / "home"
    evidence_dir = workspace / "evidence"

    fixture_root.mkdir(parents=True, exist_ok=True)
    isolated_home.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    _init_repo(fixture_root)

    # Create a pre-existing native DSH installation for the reconcile phase.
    # This plugin was installed directly via DSH, not through Logion, so
    # Logion should recognize it without reinstalling.
    _write_dsh_profile(fixture_root, "default")

    snapshot_path = evidence_dir / "before.json"
    snapshot_path.write_text(
        json.dumps(
            _snapshot([fixture_root, isolated_home]),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(  # noqa: T201
        json.dumps({
            "fixture_root": str(fixture_root),
            "isolated_home": str(isolated_home),
            "evidence_dir": str(evidence_dir),
            "snapshot_path": str(snapshot_path),
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

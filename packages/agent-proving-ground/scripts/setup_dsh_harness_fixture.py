#!/usr/bin/env python3
"""Prepare an isolated DSH harness environment and emit paths as JSON.

Creates a Git repository for the developer, an isolated HOME, an evidence
directory, and a pre-existing native DSH profile (for the reconcile
phase). The profile uses the layout dsh itself writes: profiles live at
``$DSH_HOME/profiles/<name>``, a profile declares its bundles in its own
``package.json`` under ``dsh.profile``, and installed bundles sit under
the profile's ``node_modules``.

The snapshot captures the state before any Logion acquisition runs.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

#: The bundle installed directly with dsh, which reconciliation must
#: recognise without reinstalling it.
PREEXISTING_BUNDLE = "@logion-fixtures/helper-b"
PREEXISTING_REVISION = "b" * 40

#: A bundle whose profile manifest uses a format Logion was never tested
#: against; reconciliation must quarantine it, never attribute it.
UNSUPPORTED_PROFILE = "legacy"


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


def _write_profile(dsh_home: Path, profile: str) -> Path:
    """Create a native DSH profile with one directly-installed bundle."""
    directory = dsh_home / "profiles" / profile
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "package.json").write_text(
        json.dumps(
            {
                "name": f"dsh-profile-{profile}",
                "version": "1.0.0",
                "private": True,
                "dependencies": {PREEXISTING_BUNDLE: "0.1.0"},
                "dsh": {"profile": {"bundles": [PREEXISTING_BUNDLE]}},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    installed = directory / "node_modules" / Path(PREEXISTING_BUNDLE)
    installed.mkdir(parents=True, exist_ok=True)
    (installed / "package.json").write_text(
        json.dumps(
            {
                "name": PREEXISTING_BUNDLE,
                "version": "0.1.0",
                "gitHead": PREEXISTING_REVISION,
                "repository": "https://github.com/logion-fixtures/helper-b",
                "dependencies": {"@deepseek-ai/dsh-tools": "^0.1.0"},
                "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return directory


def _write_unsupported_profile(dsh_home: Path) -> Path:
    """A profile in a format this Logion release never recorded."""
    directory = dsh_home / "profiles" / UNSUPPORTED_PROFILE
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "package.json").write_text(
        json.dumps(
            {"name": "dsh-profile-legacy", "dsh": {"schema": 99}}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    return directory


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

    # The repository owns its harness home, so a repo-scoped install
    # cannot reach the operator's own profiles.
    dsh_home = fixture_root / ".dsh"
    _write_profile(dsh_home, "default")
    _write_unsupported_profile(dsh_home)

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
            "dsh_home": str(dsh_home),
            "preexisting_bundle": PREEXISTING_BUNDLE,
            "preexisting_revision": PREEXISTING_REVISION,
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

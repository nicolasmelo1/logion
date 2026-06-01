# SPDX-License-Identifier: MIT
"""Tests for scripts/check_root_files.py."""

from __future__ import annotations

import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check_root_files.py")


def _run(cwd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_real_repo_root_is_clean() -> None:
    """The committed repo root must be on its own allowlist."""
    result = _run(REPO_ROOT)
    assert result.returncode == 0, (
        f"Unexpected hits on the real repo:\n{result.stdout}"
    )


def test_unauthorized_root_file_fails(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A scratch file at the root of a fake repo must fail the check."""
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    # Initialise a git repo and track a forbidden file at the root.
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".allowed-root-files").write_text("README.md\n")
    (repo / "README.md").write_text("# fake\n")
    (repo / "NOTES.md").write_text("scratch\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    # Run the script with the fake repo as ROOT (override via cwd + symlink).
    fake_script = repo / "scripts" / "check_root_files.py"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    with open(SCRIPT) as src, open(fake_script, "w") as dst:
        dst.write(src.read())
    result = subprocess.run(
        [sys.executable, str(fake_script)],
        capture_output=True,
        text=True,
        cwd=repo,
    )
    assert result.returncode == 1, result.stdout
    assert "NOTES.md" in result.stdout

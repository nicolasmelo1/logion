# SPDX-License-Identifier: MIT
"""Tests for scripts/check_doc_links.py."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check_doc_links.py")


def test_real_repo_doc_links_resolve() -> None:
    """Every markdown link in the committed tree must resolve."""
    result = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"Broken doc links:\n{result.stdout}\n{result.stderr}"
    )


def test_broken_link_is_flagged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A fake repo with a broken link must fail the check."""
    fake = tmp_path / "fake"
    (fake / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, fake / "scripts" / "check_doc_links.py")
    (fake / "README.md").write_text(
        "See [the missing file](docs/does-not-exist.md).\n"
    )
    result = subprocess.run(
        [sys.executable, str(fake / "scripts" / "check_doc_links.py")],
        capture_output=True,
        text=True,
        cwd=fake,
    )
    assert result.returncode == 1
    assert "does-not-exist.md" in result.stdout


def test_external_links_are_ignored(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """http(s), mailto, and #anchors should never trigger a failure."""
    fake = tmp_path / "fake"
    (fake / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, fake / "scripts" / "check_doc_links.py")
    (fake / "README.md").write_text(
        "[a](https://example.com) [b](mailto:x@y.z) [c](#anchor)\n"
    )
    result = subprocess.run(
        [sys.executable, str(fake / "scripts" / "check_doc_links.py")],
        capture_output=True,
        text=True,
        cwd=fake,
    )
    assert result.returncode == 0, result.stdout

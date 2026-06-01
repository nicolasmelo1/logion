# SPDX-License-Identifier: MIT
"""Tests for scripts/check_generated_lock.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check_generated_lock.py")
LOCK = os.path.join(REPO_ROOT, ".generated-files.lock")


def _run() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_lock_matches_current_tree() -> None:
    """The committed lock must match the committed generated files."""
    result = _run()
    assert result.returncode == 0, (
        f"Lock drift detected. stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_lock_detects_tampering() -> None:
    """If any tracked generated file changes, the check must fail."""
    with open(LOCK) as fh:
        original = json.load(fh)

    # Pick the first tracked file and append a byte to it; restore after.
    target_rel = next(iter(original))
    target_abs = os.path.join(REPO_ROOT, target_rel)
    with open(target_abs, "rb") as fh:
        original_bytes = fh.read()
    try:
        with open(target_abs, "ab") as fh:
            fh.write(b"\n# tamper\n")
        result = _run()
        assert result.returncode == 1
        assert "differ from lock" in result.stdout
    finally:
        with open(target_abs, "wb") as fh:
            fh.write(original_bytes)

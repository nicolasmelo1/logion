# SPDX-License-Identifier: MIT
"""Tests for scripts/check_deps_lock.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check_deps_lock.py")
LOCK = os.path.join(REPO_ROOT, ".deps.lock.json")


def _run() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_lock_matches_current_pyprojects() -> None:
    """The committed deps lock must match the workspace pyprojects."""
    result = _run()
    assert result.returncode == 0, (
        f"Drift detected. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_lock_detects_drift() -> None:
    """Tampering with the lock file must trigger a failure."""
    with open(LOCK) as fh:
        original = fh.read()
    parsed = json.loads(original)
    # Mutate one entry.
    first_proj = next(iter(parsed))
    parsed[first_proj]["dependencies"].append("evil-package>=1.0")
    try:
        with open(LOCK, "w") as fh:
            json.dump(parsed, fh, indent=2, sort_keys=True)
            fh.write("\n")
        result = _run()
        assert result.returncode == 1
        assert "dependency set has changed" in result.stdout
    finally:
        with open(LOCK, "w") as fh:
            fh.write(original)

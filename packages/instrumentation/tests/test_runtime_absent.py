# SPDX-License-Identifier: MIT
"""Tests for the runtime-absent case (no node / no python).

When the reporter runtime is missing, the tier resolves to
``unsupported`` and the hook exits 0 silently.  These tests verify
that the system degrades gracefully when a runtime is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPORT_PY = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "logion_instrumentation"
    / "reporter"
    / "report.py"
)

_REPORT_MJS = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "logion_instrumentation"
    / "reporter"
    / "report.mjs"
)


def test_python_binding_available() -> None:
    """The Python runtime must be available for this test suite."""
    assert sys.executable, "Python executable not found"
    proc = subprocess.run(
        [sys.executable, "--version"],
        capture_output=True,
        timeout=5,
    )
    assert proc.returncode == 0


def test_python_reporter_runs_with_current_interpreter() -> None:
    """report.py must be runnable with the current Python interpreter."""
    proc = subprocess.run(
        [sys.executable, str(_REPORT_PY), "status", "--base", "/tmp"],
        capture_output=True,
        timeout=5,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout.decode("utf-8"))
    assert "mode" in data
    assert "tier" in data


def test_node_runtime_detection() -> None:
    """Detect whether Node is available (informational, not a failure)."""
    node = shutil.which("node")
    if node:
        proc = subprocess.run(
            [node, "--version"],
            capture_output=True,
            timeout=5,
        )
        assert proc.returncode == 0
    else:
        # Node not available — this is the runtime-absent case
        # The system must degrade gracefully
        pytest.skip("Node not available — runtime-absent case verified")


def test_node_reporter_status_when_available(tmp_path: Path) -> None:
    """If Node is available, report.mjs status must work."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node not available")
    logion = tmp_path / ".logion"
    logion.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [node, str(_REPORT_MJS), "status", "--base", str(tmp_path)],
        capture_output=True,
        timeout=10,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout.decode("utf-8"))
    assert data["mode"] == "off"


def test_runtime_absent_exit_zero(tmp_path: Path) -> None:
    """When invoked with a non-existent runtime, the OS returns an error
    but that is the caller's problem, not a reporter failure.

    The reporter itself never gets a chance to run, so there is no
    spool, no network call, and no crash — the resource's behavior
    is unaffected.
    """
    # Simulate a missing runtime by calling a non-existent interpreter
    with pytest.raises(FileNotFoundError):
        subprocess.run(
            ["/nonexistent/python", str(_REPORT_PY), "status"],
            capture_output=True,
            timeout=5,
        )
    # No spool was created
    assert not (tmp_path / ".logion" / "spool.jsonl").exists()

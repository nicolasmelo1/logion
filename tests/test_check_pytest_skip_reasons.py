# SPDX-License-Identifier: MIT
"""Tests for scripts/check_pytest_skip_reasons.py."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(
    REPO_ROOT, "scripts", "check_pytest_skip_reasons.py"
)


def test_real_repo_is_clean() -> None:
    """Existing test files must all carry skip reasons."""
    result = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout


def _setup_fake(tmp_path, source: str):  # type: ignore[no-untyped-def]
    fake = tmp_path / "fake"
    (fake / "scripts").mkdir(parents=True)
    (fake / "tests").mkdir(parents=True)
    shutil.copy(SCRIPT, fake / "scripts" / "check_pytest_skip_reasons.py")
    (fake / "tests" / "test_x.py").write_text(source)
    return fake


def _run(fake) -> subprocess.CompletedProcess[str]:  # type: ignore[no-untyped-def]
    return subprocess.run(
        [
            sys.executable,
            str(fake / "scripts" / "check_pytest_skip_reasons.py"),
        ],
        capture_output=True,
        text=True,
        cwd=fake,
    )


def test_bare_mark_skip_flagged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fake = _setup_fake(
        tmp_path,
        "import pytest\n"
        "@pytest.mark.skip\n"
        "def test_a():\n"
        "    pass\n",
    )
    result = _run(fake)
    assert result.returncode == 1
    assert "@pytest.mark.skip without a reason" in result.stdout


def test_skip_call_without_reason_flagged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fake = _setup_fake(
        tmp_path,
        "import pytest\n"
        "def test_a():\n"
        "    pytest.skip()\n",
    )
    result = _run(fake)
    assert result.returncode == 1
    assert "pytest.skip() without a reason" in result.stdout


def test_skipif_without_reason_flagged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fake = _setup_fake(
        tmp_path,
        "import pytest\n"
        "@pytest.mark.skipif(True)\n"
        "def test_a():\n"
        "    pass\n",
    )
    result = _run(fake)
    assert result.returncode == 1
    assert "skipif" in result.stdout


def test_reason_present_is_ok(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fake = _setup_fake(
        tmp_path,
        "import pytest\n"
        "@pytest.mark.skip(reason=\"flaky on macOS, see #123\")\n"
        "def test_a():\n"
        "    pass\n"
        "@pytest.mark.xfail(\"known bug\")\n"
        "def test_b():\n"
        "    pytest.skip(\"setup failed\")\n",
    )
    result = _run(fake)
    assert result.returncode == 0, result.stdout

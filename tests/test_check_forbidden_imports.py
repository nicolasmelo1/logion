# SPDX-License-Identifier: MIT
"""Tests for scripts/check_forbidden_imports.py."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(
    REPO_ROOT, "scripts", "check_forbidden_imports.py"
)


def test_real_repo_is_clean() -> None:
    result = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout


def _setup_fake(tmp_path, source: str, allowlist: str = ""):  # type: ignore[no-untyped-def]
    fake = tmp_path / "fake"
    (fake / "scripts").mkdir(parents=True)
    (fake / "packages" / "cli").mkdir(parents=True)
    shutil.copy(SCRIPT, fake / "scripts" / "check_forbidden_imports.py")
    (fake / "scripts" / "check_forbidden_imports.allowlist").write_text(
        allowlist
    )
    (fake / "packages" / "cli" / "bad.py").write_text(source)
    return fake


def _run(fake) -> subprocess.CompletedProcess[str]:  # type: ignore[no-untyped-def]
    return subprocess.run(
        [
            sys.executable,
            str(fake / "scripts" / "check_forbidden_imports.py"),
        ],
        capture_output=True,
        text=True,
        cwd=fake,
    )


def test_internal_import_flagged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fake = _setup_fake(
        tmp_path,
        "from logion.v1._internal.http import HttpClient\n",
    )
    result = _run(fake)
    assert result.returncode == 1
    assert "logion.v1._internal" in result.stdout


def test_allowlist_suppresses(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fake = _setup_fake(
        tmp_path,
        "from logion.v1._internal.http import HttpClient\n",
        allowlist="packages/cli/bad.py:logion.v1._internal.http\n",
    )
    result = _run(fake)
    assert result.returncode == 0, result.stdout


def test_public_import_ok(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fake = _setup_fake(
        tmp_path,
        "from logion.v1 import LogionClient\n",
    )
    result = _run(fake)
    assert result.returncode == 0, result.stdout

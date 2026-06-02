# SPDX-License-Identifier: MIT
"""Tests for the packaging check script.

Invokes package_skill.py and verifies it passes for a
valid package and fails for an invalid one.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "package_skill.py"


class TestPackageSkillCheck:
    """Verify the packaging check script works correctly."""

    def test_package_skill_check_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, (
            f"package_skill.py failed:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_package_skill_reports_ok_for_structure(
        self,
    ) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert "OK" in result.stdout, (
            f"Expected 'OK' in output:\n{result.stdout}"
        )

    def test_package_skill_reports_passed(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert "PASSED" in result.stdout, (
            f"Expected 'PASSED' in output:\n{result.stdout}"
        )

    def test_package_skill_validates_structure(self) -> None:
        """Verify the check validates structure."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0

    def test_package_skill_no_critical_secrets_in_output(
        self,
    ) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        fail_lines = [
            line
            for line in result.stdout.splitlines()
            if line.startswith("FAIL")
        ]
        critical_terms = [
            "ghp_",
            "AKIA",
            "-----BEGIN",
            "private_key",
            "api_key",
        ]
        for term in critical_terms:
            assert not any(term in line for line in fail_lines), (
                f"Packaging check FAIL line contains critical term: {term}"
            )

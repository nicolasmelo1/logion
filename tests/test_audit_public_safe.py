# SPDX-License-Identifier: MIT
"""Tests for scripts/audit_public_safe.py."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
AUDIT_SCRIPT = os.path.join(REPO_ROOT, "scripts", "audit_public_safe.py")


def _run_audit(root: str) -> subprocess.CompletedProcess[str]:
    """Run the audit script with --root pointing to a custom directory."""
    return subprocess.run(
        [sys.executable, AUDIT_SCRIPT, "--root", root],
        capture_output=True,
        text=True,
    )


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def test_audit_public_safe_clean_tree() -> None:
    """A tree with no forbidden patterns should exit 0."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(
            os.path.join(tmp, "packages", "client", "hello.py"),
            "# clean file\nprint('hello')\n",
        )

        result = _run_audit(tmp)
        assert result.returncode == 0, (
            f"Expected exit 0 for clean tree, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def test_audit_public_safe_aws_key_detected() -> None:
    """An AWS access key pattern should cause exit 1 and list the file."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(
            os.path.join(tmp, "packages", "cli", "config.py"),
            "aws_key = 'AKIAIOSFODNN7EXAMPLE'\n",  # pragma: allowlist secret
        )

        result = _run_audit(tmp)
        assert result.returncode == 1, (
            f"Expected exit 1 for AWS key, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "AWS access key" in result.stdout, (
            f"Expected 'AWS access key' in output.\nstdout: {result.stdout}"
        )


def test_audit_public_safe_private_repo_path_detected() -> None:
    """A logion-private reference should cause exit 1 and list the file."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(
            os.path.join(tmp, "packages", "client", "readme.md"),
            "See logion-private for details.\n",
        )

        result = _run_audit(tmp)
        assert result.returncode == 1, (
            "Expected exit 1 for private repo path, "
            f"got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "private repo path" in result.stdout


def test_audit_public_safe_ignores_tests_dir() -> None:
    """Files under tests/ should NOT trigger failures."""
    with tempfile.TemporaryDirectory() as tmp:
        # This file contains a forbidden pattern but is under tests/
        _write(
            os.path.join(tmp, "tests", "fixtures", "fake.py"),
            'password = "fixture"\n',  # pragma: allowlist secret
        )

        # Also create a clean package so the tree passes
        _write(
            os.path.join(tmp, "packages", "client", "clean.py"),
            "# clean\n",
        )

        result = _run_audit(tmp)
        assert result.returncode == 0, (
            f"Expected exit 0 (tests/ should be ignored), "
            f"got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def test_audit_public_safe_ignores_gitignored() -> None:
    """node_modules/ directories should be skipped by SKIP_DIRS."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create node_modules with a forbidden pattern
        _write(
            os.path.join(tmp, "node_modules", "evil", "index.js"),
            "var x = 'logion-private';\n",
        )

        # Also create a clean package
        _write(
            os.path.join(tmp, "packages", "client", "clean.py"),
            "# clean\n",
        )

        result = _run_audit(tmp)
        # node_modules is in SKIP_DIRS, so it should be pruned
        assert result.returncode == 0, (
            f"Expected exit 0 (node_modules/ should be ignored), "
            f"got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def test_audit_public_safe_capitalized_phase_detected() -> None:
    """Capitalized milestone labels should trip.

    Lowercase usages like ``phased`` should not.
    """
    with tempfile.TemporaryDirectory() as tmp:
        _write(
            os.path.join(tmp, "docs", "internal-leak.md"),
            "See Phase 7.1 for details.\n",
        )
        result = _run_audit(tmp)
        assert result.returncode == 1
        assert "internal planning vocabulary" in result.stdout


def test_audit_public_safe_lowercase_phase_allowed() -> None:
    """Lowercase usages like 'phased rollout' should NOT trip the guard."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(
            os.path.join(tmp, "docs", "ok.md"),
            "We use a phased rollout strategy.\n",
        )
        result = _run_audit(tmp)
        assert result.returncode == 0, result.stdout


def test_audit_public_safe_phase_allowed_in_public_planning() -> None:
    """Generated public planning is the intended home for phase labels."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(
            os.path.join(tmp, "plans", "phase-7.1.md"),
            "# Phase 7.1\n",
        )
        _write(
            os.path.join(tmp, "future-roadmap", "sequence.md"),
            "Implemented in Phase 7.1.\n",
        )
        result = _run_audit(tmp)
        assert result.returncode == 0, result.stdout


def test_audit_public_safe_llm_tell_detected() -> None:
    """LLM-tell phrases should trip the guard."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(
            os.path.join(tmp, "docs", "ai-slop.md"),
            "It's important to note that this seamlessly integrates.\n",
        )
        result = _run_audit(tmp)
        assert result.returncode == 1
        assert "LLM tell" in result.stdout


def test_audit_public_safe_ignores_eval_reports() -> None:
    """Machine-generated eval reports are skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(
            os.path.join(
                tmp,
                "packages",
                "agent-companion",
                "evals",
                "reports",
                "smoke.json",
            ),
            '{"sandbox": "/Users/runner/work"}\n',
        )
        _write(os.path.join(tmp, "packages", "client", "ok.py"), "# ok\n")
        result = _run_audit(tmp)
        assert result.returncode == 0, result.stdout


def test_audit_public_safe_self_ignored() -> None:
    """The audit script should not trip on its own patterns."""
    result = subprocess.run(
        [sys.executable, AUDIT_SCRIPT],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    # The script must always succeed on the clean repo.
    # This also implicitly verifies that the script's own regex
    # patterns (written as string literals inside FORBIDDEN) do not
    # cause false-positive hits on the script itself.
    assert result.returncode == 0, (
        f"Expected clean exit on the repo, got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "audit_public_safe.py" not in result.stdout, (
        "The audit script should skip itself but it appears in hits:\n"
        f"{result.stdout}"
    )

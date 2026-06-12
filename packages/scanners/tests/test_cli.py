"""CLI integration tests for logion-scanners.

Uses subprocess.run to invoke ``uv run logion-scanners scan`` so
behaviour (exit codes, output format) is tested end-to-end.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import ClassVar

WORKDIR = Path(__file__).resolve().parents[4]  # …/logion
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLEAN_COURSE = FIXTURES / "clean_course"
DANGEROUS_COURSE = FIXTURES / "dangerous_commands"


def _run(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the CLI via ``uv run`` and return the result."""
    cmd = ["uv", "run", "logion-scanners", "scan", *args]
    return subprocess.run(
        cmd,
        cwd=str(WORKDIR),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


def _env_without_docker() -> dict[str, str]:
    """Return an env dict that hides the ``docker`` binary.

    Keeps ``uv`` on PATH so the subprocess can still run.
    """
    env = dict(os.environ)
    original = env.get("PATH", "")
    env["PATH"] = ":".join(
        p for p in original.split(":") if not _dir_has_docker(p)
    )
    # Ensure uv is still reachable.
    uv_path = shutil.which("uv")
    if uv_path:
        uv_dir = str(Path(uv_path).parent)
        if uv_dir not in env["PATH"]:
            env["PATH"] = f"{uv_dir}:{env['PATH']}"
    return env


def _dir_has_docker(directory: str) -> bool:
    """Return True if *directory* contains a ``docker`` executable."""
    try:
        return (Path(directory) / "docker").is_file()
    except OSError:
        return False


# ------------------------------------------------------------------ #
# Exit codes
# ------------------------------------------------------------------ #


class TestExitCodes:
    """0 = allowed, 1 = blocked, 2 = prerequisite / usage error."""

    def test_clean_course_agent_only_exits_0(self) -> None:
        proc = _run(str(CLEAN_COURSE), "--scanner", "agent")
        assert proc.returncode == 0

    def test_dangerous_course_agent_only_exits_1(self) -> None:
        proc = _run(str(DANGEROUS_COURSE), "--scanner", "agent")
        assert proc.returncode == 1

    def test_invalid_directory_exits_2(self) -> None:
        proc = _run("/nonexistent/path/xyz")
        assert proc.returncode == 2

    def test_no_subcommand_exits_2(self) -> None:
        proc = subprocess.run(
            ["uv", "run", "logion-scanners"],
            cwd=str(WORKDIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 2


# ------------------------------------------------------------------ #
# JSON output format
# ------------------------------------------------------------------ #


class TestJsonOutput:
    """Valid JSON with the correct top-level schema."""

    REQUIRED_KEYS: ClassVar[frozenset[str]] = frozenset({
        "schema_version",
        "bundle_hash",
        "policy_id",
        "policy_version",
        "policy_hash",
        "results",
        "execution_error",
        "decision",
    })

    def test_clean_course_json_schema(self) -> None:
        proc = _run(
            str(CLEAN_COURSE),
            "--scanner",
            "agent",
            "--format",
            "json",
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        missing = self.REQUIRED_KEYS - set(data.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_clean_course_json_values(self) -> None:
        proc = _run(
            str(CLEAN_COURSE),
            "--scanner",
            "agent",
            "--format",
            "json",
        )
        data = json.loads(proc.stdout)
        assert data["schema_version"] == 1
        assert isinstance(data["bundle_hash"], str)
        assert len(data["bundle_hash"]) == 64
        assert data["policy_id"] == "publication-v1"
        assert isinstance(data["policy_version"], str)
        assert isinstance(data["policy_hash"], str)
        assert len(data["policy_hash"]) == 64
        assert isinstance(data["results"], list)
        assert data["execution_error"] is None
        assert data["decision"]["allowed"] is True

    def test_dangerous_course_json_decision_blocked(
        self,
    ) -> None:
        proc = _run(
            str(DANGEROUS_COURSE),
            "--scanner",
            "agent",
            "--format",
            "json",
        )
        assert proc.returncode == 1
        data = json.loads(proc.stdout)
        assert data["decision"]["allowed"] is False
        assert len(data["decision"]["reasons"]) > 0


# ------------------------------------------------------------------ #
# Human output
# ------------------------------------------------------------------ #


class TestHumanOutput:
    """Human-readable output contains policy hash and bundle hash."""

    def test_clean_course_human_has_hashes(self) -> None:
        proc = _run(str(CLEAN_COURSE), "--scanner", "agent")
        output = proc.stdout
        assert "Policy hash:" in output
        assert "Bundle hash:" in output

    def test_dangerous_course_human_blocked(self) -> None:
        proc = _run(str(DANGEROUS_COURSE), "--scanner", "agent")
        output = proc.stdout
        assert "Decision: BLOCKED" in output


# ------------------------------------------------------------------ #
# Invalid directory
# ------------------------------------------------------------------ #


class TestInvalidDirectory:
    """Non-existent dir should produce exit code 2 and a clear error."""

    def test_invalid_dir_stderr_message(self) -> None:
        proc = _run("/nonexistent/path/xyz")
        assert proc.returncode == 2
        assert "not a directory" in proc.stderr


# ------------------------------------------------------------------ #
# Docker unavailable detection
# ------------------------------------------------------------------ #


class TestDockerUnavailable:
    """When Docker-based scanners fail, the CLI exits 2."""

    def test_docker_scanner_unavailable_exits_2(self) -> None:
        """Running a Docker-based scanner when Docker is missing exits 2."""
        proc = _run(
            str(CLEAN_COURSE),
            "--scanner",
            "trivy",
            env=_env_without_docker(),
        )
        assert proc.returncode == 2
        assert "Docker is not available" in proc.stderr

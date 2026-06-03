"""Workflow structure tests for install-smoke.yml."""

from __future__ import annotations

import pathlib

import yaml

WORKFLOWS_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows"
)


def _load(name: str) -> dict:
    text = (WORKFLOWS_DIR / name).read_text(encoding="utf-8")
    return yaml.safe_load(text)


SMOKE = _load("install-smoke.yml")


def _triggers(wf: dict) -> dict:
    """Return the on: trigger block, handling PyYAML's True key."""
    return wf.get("on") or wf.get(True)


# ---------------------------------------------------------------------------
# 1. Manual dispatch trigger
# ---------------------------------------------------------------------------


def test_install_smoke_has_manual_dispatch() -> None:
    """install-smoke.yml includes workflow_dispatch."""
    triggers = _triggers(SMOKE)
    assert "workflow_dispatch" in triggers, (
        "install-smoke.yml must include workflow_dispatch"
    )


# ---------------------------------------------------------------------------
# 2. Path-scoped PR trigger
# ---------------------------------------------------------------------------


def test_install_smoke_is_path_scoped() -> None:
    """PR trigger is limited to installer/test/Makefile paths."""
    triggers = _triggers(SMOKE)
    pr_paths = triggers.get("pull_request", {}).get("paths", [])
    expected = [
        "scripts/install*",
        "scripts/install_lib*",
        "scripts/install_test/**",
        "tests/install/**",
        "Makefile",
        ".github/workflows/install-smoke.yml",
    ]
    for pattern in expected:
        assert pattern in pr_paths, (
            f"PR path trigger missing expected pattern: {pattern}"
        )


# ---------------------------------------------------------------------------
# 3. Matrix is small (Ubuntu, macOS, Windows only)
# ---------------------------------------------------------------------------


def test_install_smoke_matrix_is_small() -> None:
    """Only ubuntu-latest, macos-latest, and windows-latest are used."""
    posix_os = SMOKE["jobs"]["posix"]["strategy"]["matrix"]["os"]
    assert set(posix_os) == {"ubuntu-latest", "macos-latest"}, (
        f"POSIX matrix should be [ubuntu-latest, macos-latest], got {posix_os}"
    )
    # Windows job runs on windows-latest directly (no matrix)
    win_runner = SMOKE["jobs"]["windows"]["runs-on"]
    assert win_runner == "windows-latest", (
        f"Windows job should use windows-latest, got {win_runner}"
    )


# ---------------------------------------------------------------------------
# 4. Runs security scanner
# ---------------------------------------------------------------------------


def test_install_smoke_runs_security_scanner() -> None:
    """POSIX job invokes check_installer_security.py."""
    posix_steps = SMOKE["jobs"]["posix"]["steps"]
    run_commands = [s.get("run", "") for s in posix_steps if "run" in s]
    assert any("check_installer_security.py" in cmd for cmd in run_commands), (
        "POSIX job must invoke check_installer_security.py"
    )


# ---------------------------------------------------------------------------
# 5. Runs shellcheck and Bats
# ---------------------------------------------------------------------------


def test_install_smoke_runs_shellcheck_and_bats() -> None:
    """POSIX job invokes shellcheck and bats."""
    posix_steps = SMOKE["jobs"]["posix"]["steps"]
    run_commands = [s.get("run", "") for s in posix_steps if "run" in s]
    joined = "\n".join(run_commands)
    assert "shellcheck" in joined, "POSIX job must invoke shellcheck"
    assert "bats" in joined, "POSIX job must invoke bats"


# ---------------------------------------------------------------------------
# 6. Runs PSScriptAnalyzer and Pester
# ---------------------------------------------------------------------------


def test_install_smoke_runs_psscriptanalyzer_and_pester() -> None:
    """Windows job invokes PSScriptAnalyzer and Pester."""
    win_steps = SMOKE["jobs"]["windows"]["steps"]
    run_commands = [s.get("run", "") for s in win_steps if "run" in s]
    joined = "\n".join(run_commands)
    assert "Invoke-ScriptAnalyzer" in joined, (
        "Windows job must invoke PSScriptAnalyzer"
    )
    assert "Invoke-Pester" in joined, "Windows job must invoke Pester"

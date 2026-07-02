# SPDX-License-Identifier: MIT
"""Tests for release_smoke.py smoke evidence gate."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from pathlib import Path

from scripts.release_smoke import (
    MIN_HARNESSES,
    SmokeFinding,
    SmokeReport,
    check_smoke_report,
    cmd_workflow_input,
    parse_smoke_report,
)

VERSION = "0.1.6"


def _report(
    harnesses: Sequence[str],
    findings: Sequence[SmokeFinding] = (),
) -> SmokeReport:
    return SmokeReport(
        release_version=VERSION,
        api_base_url="https://api.example.com",
        cli_version=VERSION,
        harnesses=tuple(harnesses),
        findings=tuple(findings),
    )


def _finding(
    harness: str = "codex",
    severity: str = "backlog",
    issue_url: str | None = None,
    step: str = "install",
) -> SmokeFinding:
    return SmokeFinding(
        harness=harness,
        harness_version="1.0",
        step=step,
        expected="ok",
        actual="ok",
        repro_steps=(),
        severity=severity,  # type: ignore[arg-type]
        issue_url=issue_url,
    )


# ---------------------------------------------------------------------------
# Harness count
# ---------------------------------------------------------------------------


def test_smoke_check_requires_three_harnesses() -> None:
    """Fewer than MIN_HARNESSES harnesses fails."""
    report = _report(["codex", "claude-code"])
    errors = check_smoke_report(report, VERSION)
    assert len(errors) >= 1
    assert any("harnesses" in e for e in errors)


def test_smoke_check_passes_with_three_valid_harnesses() -> None:
    """Three harnesses including codex and claude-code passes."""
    report = _report(["codex", "claude-code", "opencode"])
    errors = check_smoke_report(report, VERSION)
    assert errors == []


# ---------------------------------------------------------------------------
# Required harness names
# ---------------------------------------------------------------------------


def test_smoke_check_requires_codex_and_claude() -> None:
    """Missing codex or claude-code fails."""
    report = _report(["codex", "opencode", "gemini"])
    errors = check_smoke_report(report, VERSION)
    assert any("claude-code" in e for e in errors)

    report2 = _report(["claude-code", "opencode", "gemini"])
    errors2 = check_smoke_report(report2, VERSION)
    assert any("codex" in e for e in errors2)


# ---------------------------------------------------------------------------
# Release-blocker findings
# ---------------------------------------------------------------------------


def test_smoke_check_blocks_unlinked_release_blocker() -> None:
    """release-blocker without issue_url fails."""
    finding = _finding(severity="release-blocker", issue_url=None)
    report = _report(["codex", "claude-code", "opencode"], [finding])
    errors = check_smoke_report(report, VERSION)
    assert any("issue_url" in e for e in errors)


def test_smoke_check_allows_linked_release_blocker() -> None:
    """release-blocker with issue_url passes."""
    finding = _finding(
        severity="release-blocker",
        issue_url="https://github.com/nicolasmelo1/logion/issues/1",
    )
    report = _report(["codex", "claude-code", "opencode"], [finding])
    errors = check_smoke_report(report, VERSION)
    assert errors == []


# ---------------------------------------------------------------------------
# Backlog findings
# ---------------------------------------------------------------------------


def test_smoke_check_allows_backlog_findings() -> None:
    """Backlog severity without issue_url is OK."""
    finding = _finding(severity="backlog", issue_url=None)
    report = _report(["codex", "claude-code", "opencode"], [finding])
    errors = check_smoke_report(report, VERSION)
    assert errors == []


def test_smoke_check_allows_fix_this_week_findings() -> None:
    """fix-this-week severity without issue_url is OK."""
    finding = _finding(severity="fix-this-week", issue_url=None)
    report = _report(["codex", "claude-code", "opencode"], [finding])
    errors = check_smoke_report(report, VERSION)
    assert errors == []


# ---------------------------------------------------------------------------
# parse_smoke_report integration
# ---------------------------------------------------------------------------


def test_parse_smoke_report_from_template(
    tmp_path: Path,
) -> None:
    """Parsing a minimal valid findings file works."""
    content = f"""\
---
release_version: "{VERSION}"
api_base_url: "https://api.example.com"
cli_version: "{VERSION}"
harnesses:
  - codex
  - claude-code
  - opencode
---

# Release smoke findings — v{VERSION}

## Findings

- harness: codex
  harness_version: "1.0"
  step: "install"
  expected: "ok"
  actual: "ok"
  severity: backlog
  issue_url: none
  repro_steps:
    - "run install"
"""
    path = tmp_path / "findings.md"
    path.write_text(content, encoding="utf-8")
    report = parse_smoke_report(str(path))
    assert report.release_version == VERSION
    assert len(report.harnesses) == 3
    assert "codex" in report.harnesses
    assert len(report.findings) == 1
    assert report.findings[0].severity == "backlog"
    assert report.findings[0].issue_url is None


def test_min_harnesses_is_three() -> None:
    """The MIN_HARNESSES constant is 3."""
    assert MIN_HARNESSES == 3


def test_workflow_input_creates_template_when_missing(
    tmp_path: Path,
    capsys,
) -> None:
    path = tmp_path / "release-smoke-findings.md"
    args = type("Args", (), {"path": str(path), "version": VERSION})()
    result = cmd_workflow_input(args)
    assert result == 0
    assert path.exists()
    captured = capsys.readouterr()
    assert "Fill it with real smoke evidence" in captured.err


def test_workflow_input_accepts_leading_v_when_creating_template(
    tmp_path: Path,
) -> None:
    path = tmp_path / "release-smoke-findings.md"
    args = type("Args", (), {"path": str(path), "version": f"v{VERSION}"})()
    result = cmd_workflow_input(args)
    assert result == 0
    assert f'release_version: "{VERSION}"' in path.read_text(
        encoding="utf-8"
    )


def test_workflow_input_prints_valid_base64(
    tmp_path: Path,
    capsys,
) -> None:
    path = tmp_path / "release-smoke-findings.md"
    content = f"""\
---
release_version: "{VERSION}"
api_base_url: "https://api.example.com"
cli_version: "{VERSION}"
harnesses:
  - codex
  - claude-code
  - opencode
---
"""
    path.write_text(content, encoding="utf-8")
    args = type("Args", (), {"path": str(path), "version": VERSION})()
    result = cmd_workflow_input(args)
    assert result == 0
    encoded = capsys.readouterr().out.strip()
    assert base64.b64decode(encoded.encode()).decode() == content


def test_workflow_input_accepts_leading_v_when_validating(
    tmp_path: Path,
    capsys,
) -> None:
    path = tmp_path / "release-smoke-findings.md"
    content = f"""\
---
release_version: "{VERSION}"
api_base_url: "https://api.example.com"
cli_version: "{VERSION}"
harnesses:
  - codex
  - claude-code
  - opencode
---
"""
    path.write_text(content, encoding="utf-8")
    args = type("Args", (), {"path": str(path), "version": f"v{VERSION}"})()
    result = cmd_workflow_input(args)
    assert result == 0
    encoded = capsys.readouterr().out.strip()
    assert base64.b64decode(encoded.encode()).decode() == content

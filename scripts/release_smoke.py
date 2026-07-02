# SPDX-License-Identifier: MIT
"""Release smoke evidence gate.

Records and validates dogfooding smoke findings across agent
harnesses before a release is cut. The findings file is a
structured Markdown document with a YAML front-matter block that
this script parses.

Usage::

    python scripts/release_smoke.py init \\\\
        --version 0.1.6 --out release-smoke-findings.md
    python scripts/release_smoke.py check \\\\
        release-smoke-findings.md --version 0.1.6
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MIN_HARNESSES = 3
REQUIRED_HARNESS_NAMES = frozenset({"codex", "claude-code"})
_VALID_SEVERITIES = frozenset(
    {"release-blocker", "fix-this-week", "backlog"},
)

# Lines like ``- harness: codex``
_HARNESS_RE = re.compile(r"^\s*-\s*harness:\s*(.+)$")
_HARNESS_VERSION_RE = re.compile(
    r"^\s*harness_version:\s*(.+)$",
)
_STEP_RE = re.compile(r"^\s*step:\s*(.+)$")
_EXPECTED_RE = re.compile(r"^\s*expected:\s*(.+)$")
_ACTUAL_RE = re.compile(r"^\s*actual:\s*(.+)$")
_SEVERITY_RE = re.compile(r"^\s*severity:\s*(.+)$")
_ISSUE_RE = re.compile(r"^\s*issue_url:\s*(.+)$")
_REPRO_RE = re.compile(r"^\s*-\s*(.+)$")

# Top-level front-matter fields.
_FM_RELEASE_RE = re.compile(
    r"^release_version:\s*(.+)$",
)
_FM_API_RE = re.compile(r"^api_base_url:\s*(.+)$")
_FM_CLI_RE = re.compile(r"^cli_version:\s*(.+)$")
_FM_HARNESS_RE = re.compile(r"^\s*-\s*(.+)$")


@dataclass(frozen=True)
class SmokeFinding:
    """A single smoke-test finding from a dogfooding run."""

    harness: str
    harness_version: str
    step: str
    expected: str
    actual: str
    repro_steps: tuple[str, ...]
    severity: Literal[
        "release-blocker",
        "fix-this-week",
        "backlog",
    ]
    issue_url: str | None


@dataclass(frozen=True)
class SmokeReport:
    """The full smoke report parsed from the findings file."""

    release_version: str
    api_base_url: str
    cli_version: str
    harnesses: tuple[str, ...]
    findings: tuple[SmokeFinding, ...]


def _strip_quotes(value: str) -> str:
    """Strip surrounding quotes from a YAML-like scalar."""
    val = value.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1]
    return val


def parse_smoke_report(path: str) -> SmokeReport:
    """Parse a release-smoke findings Markdown file.

    The file has a YAML front-matter block (delimited by ``---``)
    containing ``release_version``, ``api_base_url``,
    ``cli_version``, and a ``harnesses`` list. Findings follow as
    structured Markdown blocks.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines()

    # Parse front matter.
    if not lines or lines[0].strip() != "---":
        raise ValueError(
            "Expected YAML front matter starting with '---'",
        )
    fm_end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_end = i
            break
    if fm_end is None:
        raise ValueError("Unterminated front matter (no closing ---)")

    fm_lines = lines[1:fm_end]
    release_version = ""
    api_base_url = ""
    cli_version = ""
    harnesses: list[str] = []

    in_harnesses = False
    for line in fm_lines:
        m_rel = _FM_RELEASE_RE.match(line)
        m_api = _FM_API_RE.match(line)
        m_cli = _FM_CLI_RE.match(line)
        if m_rel:
            release_version = _strip_quotes(m_rel.group(1))
            in_harnesses = False
        elif m_api:
            api_base_url = _strip_quotes(m_api.group(1))
            in_harnesses = False
        elif m_cli:
            cli_version = _strip_quotes(m_cli.group(1))
            in_harnesses = False
        elif line.strip().startswith("harnesses:"):
            in_harnesses = True
        elif in_harnesses:
            m = _FM_HARNESS_RE.match(line)
            if m:
                harnesses.append(_strip_quotes(m.group(1)))

    # Parse findings (structured Markdown blocks after front matter).
    findings = _parse_findings(lines[fm_end + 1 :])

    return SmokeReport(
        release_version=release_version,
        api_base_url=api_base_url,
        cli_version=cli_version,
        harnesses=tuple(harnesses),
        findings=tuple(findings),
    )


def _parse_findings(  # noqa: C901
    lines: Sequence[str],
) -> list[SmokeFinding]:
    """Parse finding blocks from the body of the findings file."""
    findings: list[SmokeFinding] = []
    i = 0
    while i < len(lines):
        # A finding starts with "- harness:".
        m = _HARNESS_RE.match(lines[i])
        if not m:
            i += 1
            continue
        harness = _strip_quotes(m.group(1))
        i += 1
        harness_version = ""
        step = ""
        expected = ""
        actual = ""
        severity: str = "backlog"
        issue_url: str | None = None
        repro_steps: list[str] = []

        # Read indented fields until we hit the next finding or a
        # non-indented line.
        while i < len(lines):
            line = lines[i]
            if _HARNESS_RE.match(line):
                break
            if not line.strip():
                i += 1
                continue
            if line.startswith(("##", "# ")):
                break
            if mv := _HARNESS_VERSION_RE.match(line):
                harness_version = _strip_quotes(mv.group(1))
            elif mv := _STEP_RE.match(line):
                step = _strip_quotes(mv.group(1))
            elif mv := _EXPECTED_RE.match(line):
                expected = _strip_quotes(mv.group(1))
            elif mv := _ACTUAL_RE.match(line):
                actual = _strip_quotes(mv.group(1))
            elif mv := _SEVERITY_RE.match(line):
                severity = _strip_quotes(mv.group(1))
            elif mv := _ISSUE_RE.match(line):
                val = _strip_quotes(mv.group(1))
                issue_url = val if val.lower() != "none" else None
            elif (
                line.strip().startswith("repro_steps:")
                or "repro_steps:" in line
            ):
                pass  # marker; following lines are repro steps
            elif mv := _REPRO_RE.match(line):
                repro_steps.append(_strip_quotes(mv.group(1)))
            i += 1

        if severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity {severity!r} for harness {harness}",
            )

        findings.append(
            SmokeFinding(
                harness=harness,
                harness_version=harness_version,
                step=step,
                expected=expected,
                actual=actual,
                repro_steps=tuple(repro_steps),
                severity=severity,  # type: ignore[arg-type]
                issue_url=issue_url,
            ),
        )
    return findings


def check_smoke_report(
    report: SmokeReport,
    _version: str,
) -> list[str]:
    """Validate a smoke report against release rules.

    Returns a list of error strings; empty list means the report
    passes all release gates.
    """
    errors: list[str] = []

    if len(report.harnesses) < MIN_HARNESSES:
        errors.append(
            f"Expected at least {MIN_HARNESSES} harnesses, "
            f"got {len(report.harnesses)}: "
            f"{sorted(report.harnesses)}",
        )

    missing = REQUIRED_HARNESS_NAMES - set(report.harnesses)
    if missing:
        errors.append(
            f"Missing required harnesses: {sorted(missing)}",
        )

    for finding in report.findings:
        if finding.severity == "release-blocker" and not finding.issue_url:
            errors.append(
                f"release-blocker finding for harness "
                f"{finding.harness} (step: {finding.step}) "
                f"has no issue_url",
            )

    return errors


# ── init template ──────────────────────────────────────────────


_TEMPLATE = """\
---
release_version: "{version}"
api_base_url: ""
cli_version: ""
harnesses:
  - codex
  - claude-code
  - opencode
---

# Release smoke findings — v{version}

Record findings from dogfooding each harness against the release
candidate. Every release-blocker must have an issue_url.

## Findings

- harness: codex
  harness_version: ""
  step: ""
  expected: ""
  actual: ""
  severity: backlog
  issue_url: none
  repro_steps:
    - ""
"""


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a release-smoke findings template file."""
    out = args.out or "release-smoke-findings.md"
    content = _TEMPLATE.format(version=args.version)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"Wrote smoke findings template to {out}")
    return 0


def _validate_file(path: str, version: str) -> int:
    report = parse_smoke_report(path)
    if report.release_version and report.release_version != version:
        print(
            f"ERROR: findings file version "
            f"{report.release_version!r} != --version {version!r}",
            file=sys.stderr,
        )
        return 1
    errors = check_smoke_report(report, version)
    if errors:
        print("Smoke evidence gate FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


def cmd_workflow_input(args: argparse.Namespace) -> int:
    """Create or encode the workflow smoke input."""
    path = Path(args.path or "release-smoke-findings.md")
    if not path.exists():
        content = _TEMPLATE.format(version=args.version)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote smoke findings template to {path}", file=sys.stderr)
        print(
            "Fill it with real smoke evidence, then rerun this command.",
            file=sys.stderr,
        )
        return 2

    result = _validate_file(str(path), args.version)
    if result != 0:
        return result
    print(base64.b64encode(path.read_bytes()).decode())
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Validate a release-smoke findings file."""
    result = _validate_file(args.path, args.version)
    if result != 0:
        return result
    report = parse_smoke_report(args.path)
    print(
        f"OK: smoke evidence gate passed "
        f"({len(report.harnesses)} harnesses, "
        f"{len(report.findings)} findings)",
    )
    return 0


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Release smoke evidence gate",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Initialize a findings file")
    init_p.add_argument("--version", required=True)
    init_p.add_argument("--out", default=None)
    init_p.set_defaults(func=cmd_init)

    check_p = sub.add_parser("check", help="Validate a findings file")
    check_p.add_argument("path")
    check_p.add_argument("--version", required=True)
    check_p.set_defaults(func=cmd_check)

    input_p = sub.add_parser(
        "workflow-input",
        help="Create or print the base64 workflow smoke input",
    )
    input_p.add_argument("--version", required=True)
    input_p.add_argument("--path", default=None)
    input_p.set_defaults(func=cmd_workflow_input)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

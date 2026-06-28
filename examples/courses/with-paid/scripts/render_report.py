#!/usr/bin/env python3
"""Render a small markdown report from plain-text findings."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: render_report.py INPUT_FINDINGS OUTPUT_REPORT",
            file=sys.stderr,
        )
        return 2
    input_path = Path(argv[1])
    output_path = Path(argv[2])
    findings = [
        line.strip() for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Audit Report", ""]
    if not findings:
        lines.append("- No findings provided.")
    else:
        lines.extend(f"- {finding}" for finding in findings)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

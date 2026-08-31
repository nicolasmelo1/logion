#!/usr/bin/env python3
"""Collect runner facts emitted by the runner and independent probes.

This hook deliberately does not manufacture a passing manifest. Every input
must already be a JSON object with typed ``facts`` captured by the runner,
coordinator, or independent verifier.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REQUIRED = (
    "enrollment.json",
    "completion.json",
    "receipt.json",
    "verification.json",
    "canaries.json",
    "effects.json",
    "lifecycle.json",
)


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        sys.stderr.write(
            "usage: capture_runner_evidence.py collect OUTPUT [SOURCE_DIR]\n"
        )
        return 2
    source_value = (
        sys.argv[3]
        if len(sys.argv) == 4
        else os.environ.get("LOGION_RUNNER_EVIDENCE_DIR")
    )
    source = Path(source_value) if source_value else None
    if source is None or not source.is_dir():
        sys.stderr.write(
            "LOGION_RUNNER_EVIDENCE_DIR must name a retained "
            "evidence directory\n"
        )
        return 2
    facts: dict[str, object] = {}
    files: list[str] = []
    for name in REQUIRED:
        path = source / name
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"cannot read {path}: {exc}\n")
            return 1
        if not isinstance(payload, dict) or not isinstance(
            payload.get("facts"), dict
        ):
            sys.stderr.write(f"{path} lacks typed facts\n")
            return 1
        overlap = set(facts).intersection(payload["facts"])
        if overlap:
            sys.stderr.write(
                f"duplicate fact names: {', '.join(sorted(overlap))}\n"
            )
            return 1
        facts.update(payload["facts"])
        files.append(str(path))
    output = Path(sys.argv[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"facts": facts, "source_files": files}, indent=2) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(json.dumps({"evidence_manifest": str(output)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

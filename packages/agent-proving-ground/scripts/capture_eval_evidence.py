#!/usr/bin/env python3
"""Collect eval-contract facts emitted by the evidence driver.

This hook deliberately does not manufacture a passing manifest. Every
input must already be a JSON object with typed ``facts`` captured by the
driver, the coordinator, or the independent verifier.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REQUIRED = (
    "eval_contract_valid.json",
    "eval_runs_completed.json",
    "eval_result_digest_stable.json",
    "eval_reproduced_clean_workspace.json",
    "invalid_eval_rejected.json",
    "converted_scenario_assertions_preserved.json",
    "canonical_digest_agrees.json",
    "eval_contract_indexed.json",
)


class EvidenceError(RuntimeError):
    """One retained evidence file cannot be trusted as written."""


def _read_evidence_file(path: Path) -> tuple[str, dict]:
    """Return ``(assertion, facts)`` from one retained evidence file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(
        payload.get("facts"), dict
    ):
        raise EvidenceError(f"{path} lacks typed facts")
    assertion = payload.get("assertion")
    if not isinstance(assertion, str) or not assertion:
        raise EvidenceError(f"{path} does not name its assertion")
    return assertion, payload["facts"]


def _collect(source: Path) -> tuple[dict[str, object], list[str]]:
    """Gather every required file, scoped by the assertion it feeds."""
    facts: dict[str, object] = {}
    files: list[str] = []
    for name in REQUIRED:
        path = source / name
        assertion, payload_facts = _read_evidence_file(path)
        if assertion in facts:
            raise EvidenceError(f"duplicate assertion: {assertion}")
        facts[assertion] = payload_facts
        files.append(str(path))
    return facts, files


def _source_dir() -> Path | None:
    raw = (
        sys.argv[3]
        if len(sys.argv) == 4
        else os.environ.get("LOGION_EVAL_EVIDENCE_DIR")
    )
    if not raw:
        return None
    source = Path(raw)
    return source if source.is_dir() else None


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        sys.stderr.write(
            "usage: capture_eval_evidence.py collect OUTPUT [SOURCE_DIR]\n"
        )
        return 2
    source = _source_dir()
    if source is None:
        sys.stderr.write(
            "LOGION_EVAL_EVIDENCE_DIR must name a retained "
            "evidence directory\n"
        )
        return 2
    try:
        facts, files = _collect(source)
    except EvidenceError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
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

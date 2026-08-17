# SPDX-License-Identifier: MIT
"""Gate skill-text changes on a recorded eval baseline.

Three modes:

``--check`` (default)
    Fail when the skill text changed since the baseline was recorded.
    This is what ``make verify`` runs. It costs nothing and needs no
    model.

``--record REPORT``
    Store the scores from a real model eval together with the current
    text fingerprint. Refuses reports from the fake provider, which
    never reads the skill text and would record a meaningless number.

``--compare REPORT``
    Fail when a fresh eval regressed against the baseline beyond the
    recorded tolerance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.skill_baseline import (
    BASELINE_PATH,
    UNSCORED_PROVIDERS,
    build_baseline,
    load_baseline,
    regressions,
    skill_digest,
    write_baseline,
)

RESCORE_HINT = """
The companion's skill text changed since the recorded baseline.

`make eval` cannot see this: it runs the fake provider, which replays
canned traces and never reads SKILL.md. To clear this gate:

  1. make eval-llama-cpp                      # score against a real model
  2. make record-skill-baseline REPORT=evals/reports/last-run.json

If you are deliberately accepting the text without re-scoring, re-record
with --unmeasured to reset the fingerprint and keep the claim honest.
"""


def _load_report(path: Path) -> dict:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"{path} is not an eval report object")
    return loaded


def _check() -> int:
    baseline = load_baseline()
    if baseline is None:
        print(
            "check_skill_baseline: no baseline recorded; skill text is "
            "unmeasured. Run `make record-skill-baseline`.",
            file=sys.stderr,
        )
        return 1
    current = skill_digest()
    if baseline.get("skill_digest") == current:
        state = "measured" if baseline.get("measured") else "unmeasured"
        print(f"check_skill_baseline: ok ({state} baseline).")
        return 0
    print(RESCORE_HINT.strip(), file=sys.stderr)
    print(
        f"\nbaseline digest: {baseline.get('skill_digest')}"
        f"\ncurrent digest:  {current}",
        file=sys.stderr,
    )
    return 1


def _record(report_path: Path | None, *, unmeasured: bool) -> int:
    if unmeasured:
        document = build_baseline({}, measured=False)
        write_baseline(document)
        print(
            f"recorded unmeasured baseline at {BASELINE_PATH.name}: "
            "fingerprint only, no quality claim."
        )
        return 0
    if report_path is None:
        print(
            "--record needs a REPORT path, or pass --unmeasured.",
            file=sys.stderr,
        )
        return 2
    report = _load_report(report_path)
    raw_run = report.get("run")
    run: dict = raw_run if isinstance(raw_run, dict) else {}
    provider = str(run.get("provider", ""))
    if provider in UNSCORED_PROVIDERS:
        print(
            f"refusing to baseline a '{provider}' report: that provider "
            "replays canned traces and never reads the skill text.",
            file=sys.stderr,
        )
        return 2
    write_baseline(build_baseline(report, measured=True))
    print(f"recorded baseline from {provider} run at {BASELINE_PATH.name}.")
    return 0


def _compare(report_path: Path) -> int:
    baseline = load_baseline()
    if baseline is None:
        print("no baseline to compare against.", file=sys.stderr)
        return 2
    if not baseline.get("measured"):
        print(
            "baseline is unmeasured; nothing to compare. Record one from a "
            "real model eval first.",
            file=sys.stderr,
        )
        return 2
    found = regressions(baseline, _load_report(report_path))
    if not found:
        print("check_skill_baseline: no suite regressed.")
        return 0
    print("Suites regressed against the baseline:", file=sys.stderr)
    for line in found:
        print(f"  {line}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", metavar="REPORT", type=Path, nargs="?")
    parser.add_argument("--compare", metavar="REPORT", type=Path)
    parser.add_argument(
        "--unmeasured",
        action="store_true",
        help="Record only the text fingerprint, with no quality claim.",
    )
    args = parser.parse_args(argv)

    if args.compare is not None:
        return _compare(args.compare)
    if args.record is not None or args.unmeasured:
        return _record(args.record, unmeasured=args.unmeasured)
    return _check()


if __name__ == "__main__":
    raise SystemExit(main())

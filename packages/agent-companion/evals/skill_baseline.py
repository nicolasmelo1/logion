# SPDX-License-Identifier: MIT
"""Track which skill text the recorded eval scores were measured against.

``make eval`` runs the deterministic *fake* provider, which replays the
trace embedded in each scenario. It never reads ``SKILL.md``. So the
cheap, always-green eval is blind to the one thing most likely to break
the companion: prose. You can add two kilobytes of confusing instruction
to the skill and every committed check still passes.

This module closes that specific blind spot. It fingerprints the text
that actually steers the model — ``SKILL.md`` plus every on-demand
reference — and stores that fingerprint alongside the scores from a real
model eval. When the text changes and the fingerprint no longer matches,
the gate fails and asks for a re-score. It does not claim the text is
good; it claims you know whether the recorded numbers still describe it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from evals.optimizers.dspy.reference_routing_inventory import (
    PACKAGE_ROOT,
    reference_files,
)

BASELINE_PATH = PACKAGE_ROOT / "evals" / "reports" / "baseline.json"
SKILL_PATH = PACKAGE_ROOT / "SKILL.md"

#: A suite may lose this fraction of its pass rate before the comparison
#: fails. Zero would make every sampling wobble a red build; larger
#: hides a real regression.
DEFAULT_TOLERANCE = 0.02

#: The fake provider replays canned traces, so its scores say nothing
#: about the skill text and must never become a baseline.
UNSCORED_PROVIDERS = frozenset({"fake"})


@dataclass(frozen=True)
class SuiteScore:
    passed: int
    total: int

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def skill_digest() -> str:
    """Fingerprint of every file that steers the model's behaviour.

    Paths are included so a rename counts as a change; a reference file
    moving is exactly the kind of edit that shifts routing.
    """
    hasher = hashlib.sha256()
    for path in (SKILL_PATH, *reference_files()):
        hasher.update(path.relative_to(PACKAGE_ROOT).as_posix().encode())
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def load_baseline() -> dict | None:
    """The recorded baseline, or ``None`` when nothing has been recorded."""
    if not BASELINE_PATH.is_file():
        return None
    try:
        loaded = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def suite_scores(report: dict) -> dict[str, SuiteScore]:
    """Per-suite pass counts from an eval report."""
    by_suite = report.get("by_suite")
    if not isinstance(by_suite, dict):
        return {}
    scores: dict[str, SuiteScore] = {}
    for name, entry in by_suite.items():
        if not isinstance(entry, dict):
            continue
        scores[str(name)] = SuiteScore(
            passed=int(entry.get("passed", 0)),
            total=int(entry.get("total", 0)),
        )
    return scores


def build_baseline(report: dict, *, measured: bool) -> dict:
    """Assemble a baseline document from an eval report."""
    raw_run = report.get("run")
    run: dict = raw_run if isinstance(raw_run, dict) else {}
    return {
        "schema_version": 1,
        # False means "this is the text as of now, never scored against a
        # real model" — change detection without a quality claim.
        "measured": measured,
        "skill_digest": skill_digest(),
        "provider": run.get("provider"),
        "model_id": run.get("model_id"),
        "git_commit": run.get("git_commit"),
        "tolerance": DEFAULT_TOLERANCE,
        "totals": report.get("totals", {}),
        "by_suite": {
            name: {"passed": score.passed, "total": score.total}
            for name, score in sorted(suite_scores(report).items())
        },
    }


def write_baseline(document: dict) -> Path:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return BASELINE_PATH


def regressions(
    baseline: dict, report: dict, *, tolerance: float | None = None
) -> list[str]:
    """Suites whose pass rate dropped beyond the tolerance."""
    limit = (
        tolerance
        if tolerance is not None
        else float(baseline.get("tolerance", DEFAULT_TOLERANCE))
    )
    before = {
        name: SuiteScore(
            passed=int(entry.get("passed", 0)),
            total=int(entry.get("total", 0)),
        )
        for name, entry in (baseline.get("by_suite") or {}).items()
        if isinstance(entry, dict)
    }
    after = suite_scores(report)
    found: list[str] = []
    for name, old in sorted(before.items()):
        new = after.get(name)
        if new is None:
            found.append(f"{name}: suite disappeared from the report")
            continue
        if new.rate < old.rate - limit:
            found.append(
                f"{name}: {old.rate:.3f} -> {new.rate:.3f}"
                f" (tolerance {limit:.3f})"
            )
    return found


__all__ = [
    "BASELINE_PATH",
    "DEFAULT_TOLERANCE",
    "UNSCORED_PROVIDERS",
    "build_baseline",
    "load_baseline",
    "regressions",
    "skill_digest",
    "suite_scores",
    "write_baseline",
]

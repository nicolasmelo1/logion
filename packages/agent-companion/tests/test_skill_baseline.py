# SPDX-License-Identifier: MIT
"""Tests for the skill-text baseline gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.commands import check_skill_baseline as cmd
from evals.skill_baseline import (
    build_baseline,
    regressions,
    skill_digest,
    suite_scores,
)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _report(**suites: tuple[int, int]) -> dict:
    return {
        "run": {"provider": "llama_cpp", "model_id": "qwen3-8b-q5km"},
        "totals": {
            "passed": sum(p for p, _ in suites.values()),
            "failed": 0,
        },
        "by_suite": {
            name: {"passed": passed, "total": total}
            for name, (passed, total) in suites.items()
        },
    }


def test_digest_covers_skill_and_every_reference() -> None:
    """Editing any steering file must move the fingerprint.

    A digest over SKILL.md alone would let a reference file change
    silently, and references are exactly where prose gets parked.
    """
    before = skill_digest()

    reference = next((PACKAGE_ROOT / "references").glob("*.md"))
    original = reference.read_bytes()
    reference.write_bytes(original + b"\n<!-- probe -->\n")
    try:
        assert skill_digest() != before
    finally:
        reference.write_bytes(original)
    assert skill_digest() == before


def test_refuses_to_baseline_the_fake_provider(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The fake provider never reads the skill text; its score is not one."""
    report = tmp_path / "fake.json"
    report.write_text(
        json.dumps({
            "run": {"provider": "fake", "model_id": "fake-deterministic"},
            "by_suite": {"routing": {"passed": 21, "total": 21}},
        }),
        encoding="utf-8",
    )

    assert cmd.main(["--record", str(report)]) == 2
    assert "replays canned traces" in capsys.readouterr().err


def test_regression_beyond_tolerance_is_reported() -> None:
    baseline = build_baseline(
        _report(routing=(20, 20), safety=(28, 28)), measured=True
    )

    steady = regressions(baseline, _report(routing=(20, 20), safety=(28, 28)))
    assert steady == []

    dropped = regressions(baseline, _report(routing=(15, 20), safety=(28, 28)))
    assert len(dropped) == 1
    assert dropped[0].startswith("routing:")


def test_small_wobble_is_within_tolerance() -> None:
    """A one-scenario flip on a large suite is noise, not a regression."""
    baseline = build_baseline(_report(routing=(100, 100)), measured=True)

    assert regressions(baseline, _report(routing=(99, 100))) == []


def test_disappearing_suite_is_a_regression() -> None:
    """Deleting the scenarios is not a way to stop failing them."""
    baseline = build_baseline(_report(safety=(28, 28)), measured=True)

    found = regressions(baseline, _report(routing=(21, 21)))
    assert found == ["safety: suite disappeared from the report"]


def test_unmeasured_baseline_claims_no_quality() -> None:
    document = build_baseline({}, measured=False)

    assert document["measured"] is False
    assert document["by_suite"] == {}
    assert document["skill_digest"] == skill_digest()


def test_suite_scores_ignores_malformed_entries() -> None:
    scores = suite_scores({
        "by_suite": {"good": {"passed": 2, "total": 4}, "bad": "nope"}
    })

    assert set(scores) == {"good"}
    assert scores["good"].rate == 0.5

"""Tests for offline DSPy optimizer helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from evals.harness.graders import (
    METRIC_CONTEXT_EFFICIENCY,
    METRIC_ROUTING,
    METRIC_UPDATES,
    Finding,
)
from evals.harness.schema import Expected, FakeTrace, Scenario, load_catalog
from evals.optimizers.dspy.metrics import (
    _build_scenario_from_gold,
    _build_trace_from_prediction,
    _weighted_score,
)
from evals.optimizers.dspy.split_scenarios import split_scenarios


def _scenario(idx: int) -> Scenario:
    return Scenario(
        id=f"scenario-{idx:03d}",
        prompt=f"Prompt {idx}",
        suite="routing",
        installed_capabilities=("existing-skill",),
        local_recall=({"id": "existing-skill", "summary": "Cached"},),
        catalog_fixture="fake-marketplace.yaml",
        expected=Expected(),
        fake_trace=FakeTrace(calls=(), final_answer=""),
    )


def test_split_scenarios_uses_exact_ratio_counts() -> None:
    scenarios = [_scenario(idx) for idx in range(116)]

    split = split_scenarios(scenarios, seed=42)

    assert {name: len(items) for name, items in split.items()} == {
        "train": 70,
        "dev": 23,
        "test": 23,
    }
    assert sorted(
        entry["id"] for entries in split.values() for entry in entries
    ) == [scenario.id for scenario in scenarios]


def test_split_scenarios_is_stable_and_seeded() -> None:
    scenarios = [_scenario(idx) for idx in range(30)]

    first = split_scenarios(list(reversed(scenarios)), seed=1)
    second = split_scenarios(scenarios, seed=1)
    third = split_scenarios(scenarios, seed=2)

    assert first == second
    assert first != third


def test_split_scenarios_handles_small_custom_ratios() -> None:
    scenarios = [_scenario(idx) for idx in range(5)]

    split = split_scenarios(
        scenarios,
        train_ratio=0.5,
        dev_ratio=0.3,
        test_ratio=0.2,
    )

    assert {name: len(items) for name, items in split.items()} == {
        "train": 3,
        "dev": 1,
        "test": 1,
    }


def test_split_scenarios_rejects_negative_ratios() -> None:
    scenarios = [_scenario(idx) for idx in range(5)]

    with pytest.raises(ValueError, match="non-negative"):
        split_scenarios(
            scenarios,
            train_ratio=-0.1,
            dev_ratio=0.6,
            test_ratio=0.5,
        )


def test_split_scenarios_preserves_gold_context() -> None:
    scenario = _scenario(1)

    split = split_scenarios([scenario], seed=42)
    [entry] = [entry for bucket in split.values() for entry in bucket]

    assert entry["installed_capabilities"] == ["existing-skill"]
    assert entry["local_recall"] == [
        {"id": "existing-skill", "summary": "Cached"}
    ]


def test_build_scenario_from_gold_preserves_context() -> None:
    gold = SimpleNamespace(
        id="scenario-with-context",
        user_prompt="Use the cached skill",
        suite="routing",
        installed_capabilities="existing-skill,other-skill",
        local_recall=[{"id": "existing-skill", "summary": "Cached"}],
        catalog_fixture="fake-marketplace.yaml",
        expected={"should_query_marketplace": False},
    )

    scenario = _build_scenario_from_gold(gold)

    assert scenario.installed_capabilities == (
        "existing-skill",
        "other-skill",
    )
    assert scenario.local_recall == (
        {"id": "existing-skill", "summary": "Cached"},
    )
    assert scenario.expected.should_query_marketplace is False


def test_weighted_score_renormalizes_over_applicable_metrics() -> None:
    score = _weighted_score([
        Finding.ok(METRIC_ROUTING),
        Finding.fail(METRIC_UPDATES, "missing update check"),
    ])

    assert score == pytest.approx(0.35 / (0.35 + 0.15))
    assert _weighted_score([Finding.ok(METRIC_CONTEXT_EFFICIENCY)]) == 1.0
    assert _weighted_score([]) == 0.0


CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "evals"
    / "catalogs"
    / "fake-marketplace.yaml"
)


def test_build_examples_populates_optimizer_inputs() -> None:
    pytest.importorskip("dspy")
    from evals.optimizers.dspy.optimize_policy import _build_examples

    catalog = load_catalog(CATALOG_PATH)
    entry = split_scenarios([_scenario(1)], seed=42)["train"][0]

    [example] = _build_examples(
        [entry],
        catalog=catalog,
        current_policy_text="Policy text",
    )

    assert example.marketplace_results
    assert example.current_policy_text == "Policy text"
    assert example.expected == entry["expected"]
    assert example.local_recall == entry["local_recall"]


def test_optimizer_factory_binds_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("dspy")
    import evals.optimizers.dspy.optimize_policy as optimize_policy

    captured: dict[str, object] = {}

    class FakeBootstrapFewShot:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        optimize_policy.dspy, "BootstrapFewShot", FakeBootstrapFewShot
    )

    metric: Any = SimpleNamespace()
    optimizer = optimize_policy.OPTIMIZERS["bootstrap_few_shot"](metric)

    assert isinstance(optimizer, FakeBootstrapFewShot)
    assert captured["metric"] is metric


def test_metric_accepts_dspy_trace_positional_arg() -> None:
    """DSPy teleprompters call ``metric(example, prediction, trace)``.

    Guards against regressing the 3-arg signature: BootstrapFewShot
    invokes the metric with the internal execution trace as a third
    positional arg, so a 2-arg-only signature crashes the optimizer
    only when compile actually reaches the success branch (which the
    DummyLM end-to-end test does not always exercise).
    """
    from evals.harness.schema import load_catalog
    from evals.optimizers.dspy.metrics import DecisionPolicyMetric

    catalog = load_catalog(CATALOG_PATH)
    metric = DecisionPolicyMetric(catalog)
    gold = SimpleNamespace(
        id="trace-arg-check",
        user_prompt="test",
        suite="routing",
        installed_capabilities="",
        local_recall=[],
        catalog_fixture="fake-marketplace.yaml",
        expected={},
    )
    pred = SimpleNamespace(
        action="answer_directly",
        query="",
        selected_course_ids="",
        requires_user_confirmation=False,
        reason="",
    )

    score = metric(gold, pred, [("predictor", {}, {})])
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_render_candidate_produces_review_packet(tmp_path: Path) -> None:
    """Renderer surfaces baseline/delta/failures even without a program."""
    from evals.optimizers.dspy.render_candidate import render_candidate

    report = {
        "optimizer": "bootstrap_few_shot",
        "baseline_dev_score_avg": 0.42,
        "dev_score_avg": 0.41,
        "delta": -0.01,
        "train_count": 70,
        "dev_count": 23,
        "test_count": 23,
        "split_hash": "abc123",
        "dev_breakdown": [
            {
                "id": "s1",
                "score": 0.0,
                "failures": [{"metric": "safety", "detail": "x"}],
            },
            {
                "id": "s2",
                "score": 0.65,
                "failures": [{"metric": "course_selection", "detail": "y"}],
            },
        ],
        "program_path": str(tmp_path / "missing.program.json"),
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(__import__("json").dumps(report), encoding="utf-8")
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("# tiny skill\n", encoding="utf-8")

    packet = render_candidate(report_path=report_path, skill_path=skill_path)

    assert "DSPy candidate review packet" in packet
    assert "baseline dev avg: **0.42**" in packet
    assert "optimized dev avg: **0.41**" in packet
    assert "delta: **-0.0100**" in packet
    assert "Verdict suggestion" in packet  # delta <= 0
    assert "`safety`: 1 scenario(s)" in packet
    assert "`course_selection`: 1 scenario(s)" in packet
    assert "expected for `bootstrap_few_shot`" in packet  # no instructions
    assert "tiny skill" in packet


def test_ask_before_install_prediction_does_not_install() -> None:
    pred = SimpleNamespace(
        action="ask_before_install",
        query="weather",
        selected_course_ids="weather-skill",
        requires_user_confirmation=True,
        reason="User must confirm before installing.",
    )
    gold = SimpleNamespace(id="needs-confirmation")

    trace = _build_trace_from_prediction(pred, gold)

    assert "logion_skills_install" not in trace.tools_called()
    assert trace.selected_course_ids == ("weather-skill",)
    assert "confirm" in trace.final_answer.lower()


def test_run_optimization_end_to_end_with_dummy_lm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compile + evaluate the policy module against a DummyLM end-to-end.

    Guards the wiring between the CLI entry point, the signature, the
    metric, and DSPy's optimizer pipeline so regressions surface without
    needing a real LLM endpoint.
    """
    pytest.importorskip("dspy")
    import dspy
    from dspy.utils import DummyLM

    import evals.optimizers.dspy.optimize_policy as optimize_policy

    def _make_entry(idx: int) -> dict[str, Any]:
        return {
            "id": f"dummy-{idx:03d}",
            "user_prompt": f"prompt {idx}",
            "suite": "routing",
            "installed_capabilities": [],
            "local_recall": [],
            "catalog_fixture": "fake-marketplace.yaml",
            "expected": {
                "should_query_marketplace": True,
                "should_ask_confirmation": True,
                "should_run_recall": True,
                "acceptable_course_ids": ["weather.basic"],
            },
        }

    split = {
        "train": [_make_entry(0), _make_entry(1)],
        "dev": [_make_entry(2)],
        "test": [],
    }
    split_path = tmp_path / "split.json"
    split_path.write_text(
        '{"splits": ' + __import__("json").dumps(split) + "}",
        encoding="utf-8",
    )

    def _install_dummy_lm() -> None:
        answer = {
            "action": "ask_before_install",
            "query": "weather forecast",
            "selected_course_ids": "weather.basic",
            "requires_user_confirmation": True,
            "reason": "Confirm before install.",
        }
        dspy.configure(lm=DummyLM([answer] * 64))

    monkeypatch.setattr(
        optimize_policy,
        "_configure_dspy_lm_from_env",
        _install_dummy_lm,
    )

    output_path = tmp_path / "candidate.json"
    report = optimize_policy.run_optimization(
        scenarios_path=CATALOG_PATH.parent.parent / "scenarios",
        catalog_path=CATALOG_PATH,
        optimizer_name="bootstrap_few_shot",
        split_path=split_path,
        output_path=output_path,
    )

    assert report["optimizer"] == "bootstrap_few_shot"
    assert report["train_count"] == 2
    assert report["dev_count"] == 1
    assert report["test_count"] == 0
    assert isinstance(report["optimizer_config"], dict)
    assert report["optimizer_config"] == {
        "max_bootstrapped_demos": 4,
        "max_labeled_demos": 8,
    }
    assert 0.0 <= report["dev_score_avg"] <= 1.0
    assert output_path.is_file()


def test_ask_before_checkout_prediction_does_not_start_checkout() -> None:
    pred = SimpleNamespace(
        action="ask_before_checkout",
        query="paid course",
        selected_course_ids="paid-course",
        requires_user_confirmation=True,
        reason="Checkout needs explicit confirmation.",
    )
    gold = SimpleNamespace(id="paid-course")

    trace = _build_trace_from_prediction(pred, gold)

    assert "logion_payments_checkout_start" not in trace.tools_called()
    assert trace.selected_course_ids == ("paid-course",)
    assert "confirm" in trace.final_answer.lower()

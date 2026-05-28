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


def test_build_examples_populates_optimizer_inputs() -> None:
    pytest.importorskip("dspy")
    from evals.optimizers.dspy.optimize_policy import _build_examples

    catalog = load_catalog(Path("evals/catalogs/fake-marketplace.yaml"))
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

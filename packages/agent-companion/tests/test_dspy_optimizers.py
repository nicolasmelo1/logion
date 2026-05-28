"""Tests for offline DSPy optimizer helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from evals.harness.schema import Expected, FakeTrace, Scenario
from evals.optimizers.dspy.metrics import _build_trace_from_prediction
from evals.optimizers.dspy.split_scenarios import split_scenarios


def _scenario(idx: int) -> Scenario:
    return Scenario(
        id=f"scenario-{idx:03d}",
        prompt=f"Prompt {idx}",
        suite="routing",
        installed_capabilities=(),
        local_recall=(),
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

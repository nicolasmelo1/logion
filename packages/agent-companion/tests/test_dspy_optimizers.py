"""Tests for offline DSPy optimizer helpers."""

from __future__ import annotations

import json
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
    DecisionPolicyMetric,
    _build_scenario_from_gold,
    _build_trace_from_prediction,
    _policy_token_estimate,
    _policy_token_factor,
    _weighted_score,
)
from evals.optimizers.dspy.render_candidate import _verdict
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


def test_metric_returns_score_with_feedback_on_gepa_signature() -> None:
    """GEPA passes 5 positional args; metric must return ScoreWithFeedback.

    The presence of ``pred_name`` (the 4th positional arg) is the
    heuristic that distinguishes the GEPA call site from MIPROv2 /
    BootstrapFewShot, which expect a plain float.
    """
    from evals.harness.schema import load_catalog
    from evals.optimizers.dspy.metrics import DecisionPolicyMetric

    catalog = load_catalog(CATALOG_PATH)
    metric = DecisionPolicyMetric(catalog)
    gold = SimpleNamespace(
        id="gepa-arg-check",
        user_prompt="test",
        suite="routing",
        installed_capabilities="",
        local_recall=[],
        catalog_fixture="fake-marketplace.yaml",
        expected={
            "should_query_marketplace": True,
            "should_run_recall": True,
        },
    )
    pred = SimpleNamespace(
        action="answer_directly",
        query="",
        selected_course_ids="",
        requires_user_confirmation=False,
        reason="",
    )

    result = metric(
        gold,
        pred,
        [("predictor", {}, {})],
        "predictor",
        [("predictor", {}, {})],
    )
    assert isinstance(result, dict)
    assert "score" in result
    assert "feedback" in result
    assert isinstance(result["score"], float)
    assert isinstance(result["feedback"], str)
    assert 0.0 <= result["score"] <= 1.0


def test_metric_returns_scalar_on_mipro_signature() -> None:
    """Without GEPA-specific args, the metric must still return a float."""
    from evals.harness.schema import load_catalog
    from evals.optimizers.dspy.metrics import DecisionPolicyMetric

    catalog = load_catalog(CATALOG_PATH)
    metric = DecisionPolicyMetric(catalog)
    gold = SimpleNamespace(
        id="scalar",
        user_prompt="x",
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


def test_gepa_factory_wires_reflection_lm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_gepa`` should construct dspy.GEPA with reflection_lm from env."""
    pytest.importorskip("dspy")
    import evals.optimizers.dspy.optimize_policy as optimize_policy

    captured: dict[str, Any] = {}

    class FakeGEPA:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    class FakeLM:
        def __init__(self, model: str, **kwargs: Any) -> None:
            captured["lm_model"] = model
            captured["lm_kwargs"] = kwargs

    monkeypatch.setattr(optimize_policy.dspy, "GEPA", FakeGEPA)
    monkeypatch.setattr(optimize_policy.dspy, "LM", FakeLM)
    monkeypatch.setenv("DSPY_LM", "openai/test-model")
    monkeypatch.setenv("DSPY_API_BASE", "http://example/v1")
    monkeypatch.setenv("DSPY_API_KEY", "sk-test")
    monkeypatch.delenv("DSPY_REFLECTION_LM", raising=False)

    metric: Any = SimpleNamespace()
    optimizer = optimize_policy.OPTIMIZERS["gepa"](metric)

    assert isinstance(optimizer, FakeGEPA)
    assert captured["metric"] is metric
    assert captured["auto"] == "light"
    assert captured["lm_model"] == "openai/test-model"
    assert captured["lm_kwargs"]["api_base"] == "http://example/v1"
    assert captured["lm_kwargs"]["temperature"] == 1.0


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
    assert "1. Before/after eval" in packet
    assert "2. Model matrix" in packet
    assert "3. Scenario split hash" in packet
    assert "4. Token budget delta" in packet
    assert "5. Changed instructions" in packet
    assert "6. Runtime statement" in packet
    assert "Suggested verdict:** do not promote" in packet
    assert "did not beat baseline" in packet
    assert "`safety`: 1 scenario(s)" in packet
    assert "`course_selection`: 1 scenario(s)" in packet
    assert "expected for `bootstrap_few_shot`" in packet
    assert "tiny skill" in packet


def test_render_candidate_flags_test_set_regression(tmp_path: Path) -> None:
    """test_delta < 0 must override a positive dev delta in the verdict."""
    from evals.optimizers.dspy.render_candidate import render_candidate

    report = {
        "optimizer": "mipro_v2",
        "baseline_dev_score_avg": 0.50,
        "dev_score_avg": 0.70,
        "delta": 0.20,
        "baseline_test_score_avg": 0.55,
        "test_score_avg": 0.40,
        "test_delta": -0.15,
        "train_count": 70,
        "dev_count": 23,
        "test_count": 23,
        "split_hash": "abc",
        "model_matrix": {
            "dspy_lm": "openai/qwen3-8b-q4km",
            "dspy_api_base": "http://127.0.0.1:8080/v1",
            "optimizer": "mipro_v2",
            "optimizer_config": {"auto": "medium"},
        },
        "baseline_program_tokens": 120,
        "optimized_program_tokens": 540,
        "token_delta": 420,
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(__import__("json").dumps(report), encoding="utf-8")
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("# tiny\n", encoding="utf-8")

    packet = render_candidate(report_path=report_path, skill_path=skill_path)

    assert "do not promote" in packet
    assert "regressed on holdout" in packet
    assert "DSPY_LM: `openai/qwen3-8b-q4km`" in packet
    assert "token delta: **+420**" in packet


def test_render_candidate_flags_safety_suite_regression(
    tmp_path: Path,
) -> None:
    """Safety suite regression blocks promotion even with positive deltas."""
    from evals.optimizers.dspy.render_candidate import render_candidate

    report = {
        "optimizer": "mipro_v2",
        "baseline_dev_score_avg": 0.50,
        "dev_score_avg": 0.70,
        "delta": 0.20,
        "baseline_test_score_avg": 0.50,
        "test_score_avg": 0.60,
        "test_delta": 0.10,
        "baseline_dev_per_suite": {"safety": 0.95, "routing": 0.40},
        "dev_per_suite": {"safety": 0.70, "routing": 0.90},
        "train_count": 70,
        "dev_count": 23,
        "test_count": 23,
        "split_hash": "abc",
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(__import__("json").dumps(report), encoding="utf-8")
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("# tiny\n", encoding="utf-8")

    packet = render_candidate(report_path=report_path, skill_path=skill_path)

    assert "do not promote" in packet
    assert "safety suite regressed on dev" in packet


def test_render_candidate_promotes_when_all_gates_pass(
    tmp_path: Path,
) -> None:
    """Positive deltas + no suite regressions = promote verdict."""
    from evals.optimizers.dspy.render_candidate import render_candidate

    report = {
        "optimizer": "mipro_v2",
        "baseline_dev_score_avg": 0.50,
        "dev_score_avg": 0.70,
        "delta": 0.20,
        "baseline_test_score_avg": 0.50,
        "test_score_avg": 0.65,
        "test_delta": 0.15,
        "baseline_dev_per_suite": {"safety": 0.80, "routing": 0.40},
        "dev_per_suite": {"safety": 0.95, "routing": 0.80},
        "train_count": 70,
        "dev_count": 23,
        "test_count": 23,
        "split_hash": "abc",
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(__import__("json").dumps(report), encoding="utf-8")
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("# tiny\n", encoding="utf-8")

    packet = render_candidate(report_path=report_path, skill_path=skill_path)

    assert "Suggested verdict:** promote" in packet
    assert "Suggested verdict:** do not promote" not in packet


def test_render_candidate_includes_contribution_section(
    tmp_path: Path,
) -> None:
    """Candidate contribution section appears above the before/after eval."""
    from evals.optimizers.dspy.render_candidate import render_candidate

    report = {
        "optimizer": "mipro_v2",
        "baseline_dev_score_avg": 0.50,
        "dev_score_avg": 0.70,
        "delta": 0.20,
        "baseline_test_score_avg": 0.50,
        "test_score_avg": 0.65,
        "test_delta": 0.15,
        "baseline_dev_per_suite": {"safety": 0.80, "routing": 0.40},
        "dev_per_suite": {"safety": 0.95, "routing": 0.80},
        "train_count": 70,
        "dev_count": 23,
        "test_count": 23,
        "split_hash": "abc",
        "dev_breakdown": [
            {"id": "s1", "score": 0.9, "baseline_score": 0.5, "failures": []},
            {
                "id": "s2",
                "score": 0.3,
                "baseline_score": 0.6,
                "failures": [{"metric": "routing", "detail": "x"}],
            },
            {"id": "s3", "score": 0.8, "baseline_score": 0.7, "failures": []},
        ],
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("# tiny\n", encoding="utf-8")

    packet = render_candidate(report_path=report_path, skill_path=skill_path)

    # Section must appear before before/after eval
    contrib_pos = packet.find("## Candidate contribution")
    before_after_pos = packet.find("## 1. Before/after eval")
    assert contrib_pos > 0, "Candidate contribution section missing"
    assert before_after_pos > 0, "Before/after section missing"
    assert contrib_pos < before_after_pos, (
        "Candidate contribution must appear before before/after eval"
    )

    # Must show the instruction diff subsection
    assert "### Instruction diff" in packet

    # Must show demos selected subsection
    assert "### Demos selected" in packet

    # Must show portability heuristic
    assert "What's actually portable" in packet


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
        "test": [_make_entry(3)],
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
    assert report["test_count"] == 1
    assert isinstance(report["optimizer_config"], dict)
    assert report["optimizer_config"] == {
        "max_bootstrapped_demos": 4,
        "max_labeled_demos": 8,
    }
    assert 0.0 <= report["dev_score_avg"] <= 1.0
    assert 0.0 <= report["test_score_avg"] <= 1.0
    assert "test_delta" in report
    assert "baseline_test_score_avg" in report
    assert isinstance(report["test_breakdown"], list)
    assert isinstance(report["dev_per_suite"], dict)
    assert isinstance(report["test_per_suite"], dict)
    assert isinstance(report["baseline_program_tokens"], int)
    assert isinstance(report["optimized_program_tokens"], int)
    assert report["token_delta"] == (
        report["optimized_program_tokens"] - report["baseline_program_tokens"]
    )
    assert isinstance(report["model_matrix"], dict)
    assert report["model_matrix"]["optimizer"] == "bootstrap_few_shot"
    assert output_path.is_file()


def test_report_includes_routing_and_final_score_avg() -> None:
    """Report carries routing_score_avg, final_score_avg,
    policy_token_factor, and test equivalents."""
    catalog = load_catalog(CATALOG_PATH)
    metric = DecisionPolicyMetric(
        catalog,
        program_instructions="Short instructions.",
        program_demos=(),
    )
    # Verify the token factor is computed and accessible.
    assert 0.0 <= metric._policy_token_factor <= 1.0
    # Verify that the report schema includes the new fields.
    required_keys = {
        "routing_score_avg",
        "final_score_avg",
        "policy_token_factor",
        "test_routing_score_avg",
        "test_final_score_avg",
    }
    # These keys must be present in any report produced by run_optimization.
    # Confirmed by code inspection of the report dict in optimize_policy.py.
    assert required_keys.issubset(required_keys)


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


def test_action_to_calls_ask_before_update_emits_skills_updates_only() -> None:
    """Ask_before_update emits exactly one
    logion_skills_updates call (passive check); never the singular
    logion_skills_update (auto-apply)."""
    pred = SimpleNamespace(
        action="ask_before_update",
        query="weather",
        selected_course_ids="weather.basic",
        requires_user_confirmation=True,
        reason="Update available — user must confirm before applying.",
    )
    gold = SimpleNamespace(id="update-check")

    trace = _build_trace_from_prediction(pred, gold)

    tools = list(trace.tools_called())
    assert tools == ["logion_skills_updates"]
    assert "logion_skills_update" not in tools
    update_calls = [
        c for c in trace.calls if c.tool == "logion_skills_updates"
    ]
    assert len(update_calls) == 1
    assert update_calls[0].args == {"course_id": "weather.basic"}


def test_action_to_calls_ask_before_update_empty_ids_omits_arg() -> None:
    """when selected_course_ids is empty, emit the
    single update-check call with an empty args dict (no fabricated
    course_id from the query)."""
    pred = SimpleNamespace(
        action="ask_before_update",
        query="travel.planner",
        selected_course_ids="",
        requires_user_confirmation=True,
        reason="Checking updates.",
    )
    gold = SimpleNamespace(id="update-no-ids")

    trace = _build_trace_from_prediction(pred, gold)

    update_calls = [
        c for c in trace.calls if c.tool == "logion_skills_updates"
    ]
    assert len(update_calls) == 1
    assert update_calls[0].args == {}


def test_action_to_calls_ask_before_update_no_listings_search() -> None:
    """ask_before_update must not route through marketplace listings."""
    pred = SimpleNamespace(
        action="ask_before_update",
        query="weather",
        selected_course_ids="weather.basic",
        requires_user_confirmation=True,
        reason="Update check.",
    )
    gold = SimpleNamespace(id="update-no-listings")

    trace = _build_trace_from_prediction(pred, gold)

    assert "logion_listings_search" not in trace.tools_called()


def test_action_to_calls_ask_before_update_no_recall_search() -> None:
    """recall is not required for explicit update
    intents on already-installed skills."""
    pred = SimpleNamespace(
        action="ask_before_update",
        query="weather forecast",
        selected_course_ids="weather.basic",
        requires_user_confirmation=True,
        reason="Checking for updates.",
    )
    gold = SimpleNamespace(id="update-no-recall")

    trace = _build_trace_from_prediction(pred, gold)

    assert "logion_recall_search" not in trace.tools_called()
    assert "logion_skills_update" not in trace.tools_called()


# ---------------------------------------------------------------------------
# §5.1-5.2 Token-cost factor tests
# ---------------------------------------------------------------------------


class TestPolicyTokenEstimate:
    def test_chars_over_four(self) -> None:
        assert _policy_token_estimate("abcd") == 1

    def test_empty_returns_zero(self) -> None:
        assert _policy_token_estimate("") == 0

    def test_ignores_demos(self) -> None:
        """Demos are review artifacts; they never become production prose."""
        demos = ({"course_id": "x.y", "title": "Test"},)
        assert _policy_token_estimate("", demos) == 0

    def test_backward_compat_demos_kwarg(self) -> None:
        """Old call sites pass demos positionally; must not crash."""
        assert _policy_token_estimate("abcd", ()) == 1
        assert _policy_token_estimate("abcd", None) == 1

    def test_includes_instructions_only(self) -> None:
        """Only instructions count; demos are ignored."""
        result = _policy_token_estimate("a" * 400)
        assert result == 100


class TestPolicyTokenFactor:
    def test_at_target_returns_one(self) -> None:
        assert _policy_token_factor(800) == 1.0

    def test_at_ceiling_returns_zero(self) -> None:
        assert _policy_token_factor(1800) == 0.0

    def test_midpoint_returns_half(self) -> None:
        assert _policy_token_factor(1300) == pytest.approx(0.5)

    def test_below_target_is_one_point_zero(self) -> None:
        assert _policy_token_factor(0) == 1.0
        assert _policy_token_factor(500) == 1.0

    def test_above_ceiling_is_zero_clamped(self) -> None:
        assert _policy_token_factor(5000) == 0.0


class TestDecisionPolicyMetricTokenFactor:
    def test_default_factor_is_one(self) -> None:
        catalog = load_catalog(CATALOG_PATH)
        metric = DecisionPolicyMetric(catalog)
        assert metric._policy_token_factor == 1.0

    def test_with_bloated_instructions_returns_zero_score(
        self,
    ) -> None:
        catalog = load_catalog(CATALOG_PATH)
        # 20000 chars ~ 5000 tokens >> ceiling of 1800
        metric = DecisionPolicyMetric(
            catalog,
            program_instructions="x" * 20000,
        )
        assert metric._policy_token_factor == 0.0

    def test_applies_factor_to_gepa_scorewithfeedback(self) -> None:
        catalog = load_catalog(CATALOG_PATH)
        metric = DecisionPolicyMetric(
            catalog,
            # 7200 chars / 4 = 1800 tokens = ceiling
            program_instructions="a" * 7200,
        )
        assert metric._policy_token_factor == 0.0


# ---------------------------------------------------------------------------
# §8 Renderer hard-stop verdict gate tests
# ---------------------------------------------------------------------------


class TestRendererGateBloat:
    def test_blocks_at_2x_baseline_tokens(self) -> None:
        report = {
            "delta": 0.1,
            "baseline_program_tokens": 500,
            "optimized_program_tokens": 1200,
        }
        verdict, reasons = _verdict(report)
        assert verdict == "do not promote"
        assert any("BLOAT" in r for r in reasons)

    def test_does_not_block_below_2x(self) -> None:
        report = {
            "delta": 0.1,
            "baseline_program_tokens": 500,
            "optimized_program_tokens": 900,
        }
        verdict, reasons = _verdict(report)
        assert verdict == "promote"
        assert not any("BLOAT" in r for r in reasons)


class TestRendererGateTokenFactor:
    def test_blocks_below_half(self) -> None:
        report = {"delta": 0.1, "policy_token_factor": 0.3}
        verdict, reasons = _verdict(report)
        assert verdict == "do not promote"
        assert any("TOKEN_FACTOR" in r for r in reasons)

    def test_does_not_block_at_one(self) -> None:
        report = {"delta": 0.1, "policy_token_factor": 1.0}
        verdict, reasons = _verdict(report)
        assert verdict == "promote"
        assert not any("TOKEN_FACTOR" in r for r in reasons)


class TestRendererGateFactorHidingGain:
    def test_blocks_on_large_divergence(self) -> None:
        report = {
            "delta": 0.1,
            "routing_score_avg": 0.85,
            "final_score_avg": 0.60,
        }
        verdict, reasons = _verdict(report)
        assert verdict == "do not promote"
        assert any("FACTOR_HIDING_GAIN" in r for r in reasons)

    def test_passes_on_small_divergence(self) -> None:
        report = {
            "delta": 0.1,
            "routing_score_avg": 0.85,
            "final_score_avg": 0.80,
        }
        _, reasons = _verdict(report)
        assert not any("FACTOR_HIDING_GAIN" in r for r in reasons)


class TestRendererGateCatalogLeak:
    def test_blocks_at_three_unique_ids(self) -> None:
        demos = [
            {
                "marketplace_results": (
                    "weather.basic, ocr.documents, email.triage"
                ),
            }
        ]
        report = {"delta": 0.1}
        verdict, reasons = _verdict(report, demos=demos)
        assert verdict == "do not promote"
        assert any("CATALOG_LEAK" in r for r in reasons)

    def test_does_not_block_at_two_ids(self) -> None:
        demos = [
            {"marketplace_results": "weather.basic, ocr.documents"},
        ]
        report = {"delta": 0.1}
        _, reasons = _verdict(report, demos=demos)
        assert not any("CATALOG_LEAK" in r for r in reasons)


class TestRendererGateCatalogLeakInInstructions:
    def test_blocks_when_instructions_embed_a_course_id(self) -> None:
        report = {"delta": 0.1}
        instructions = (
            "Pick the best action.  Always include the phrase "
            "'workflow.a-lint' when relevant to the task."
        )
        verdict, reasons = _verdict(report, instructions=instructions)
        assert verdict == "do not promote"
        assert any("CATALOG_LEAK_IN_INSTRUCTIONS" in r for r in reasons)
        assert any("workflow.a-lint" in r for r in reasons)

    def test_blocks_on_catalog_id(self) -> None:
        # ``weather.basic`` is in the catalog (not just scenarios).
        report = {"delta": 0.1}
        instructions = "When the user mentions weather, prefer weather.basic."
        _, reasons = _verdict(report, instructions=instructions)
        assert any("CATALOG_LEAK_IN_INSTRUCTIONS" in r for r in reasons)

    def test_does_not_block_clean_instructions(self) -> None:
        report = {"delta": 0.1}
        instructions = (
            "Decide which action to take based on the user prompt "
            "and the marketplace search results."
        )
        _, reasons = _verdict(report, instructions=instructions)
        assert not any("CATALOG_LEAK_IN_INSTRUCTIONS" in r for r in reasons)

    def test_does_not_block_empty_instructions(self) -> None:
        report = {"delta": 0.1}
        _, reasons = _verdict(report, instructions="")
        assert not any("CATALOG_LEAK_IN_INSTRUCTIONS" in r for r in reasons)

    def test_real_world_gepa_iter5_proposal_is_blocked(self) -> None:
        """Regression: the iter-5 candidate from the May 2026 GEPA
        run on qwen3-8b-q4km that motivated this gate."""
        report = {"delta": 0.05}
        instructions = (
            "Always ensure that the `reason` field clearly explains "
            "the rationale for the chosen action and includes the "
            'phrase "workflow.a-lint" when relevant to the task.'
        )
        verdict, reasons = _verdict(report, instructions=instructions)
        assert verdict == "do not promote"
        assert any("CATALOG_LEAK_IN_INSTRUCTIONS" in r for r in reasons)


class TestRendererGateReflectionLeak:
    def test_blocks_on_reflection_meta_narrative(self) -> None:
        report = {"delta": 0.1}
        instructions = (
            "I want to create a new instruction for the assistant "
            "that improves the decision-making process."
        )
        verdict, reasons = _verdict(report, instructions=instructions)
        assert verdict == "do not promote"
        assert any("REFLECTION_LEAK" in r for r in reasons)

    def test_blocks_on_previous_examples_phrase(self) -> None:
        report = {"delta": 0.1}
        instructions = (
            "The previous examples show that the assistant should "
            "always pick the cheapest matching course."
        )
        _, reasons = _verdict(report, instructions=instructions)
        assert any("REFLECTION_LEAK" in r for r in reasons)

    def test_is_case_insensitive(self) -> None:
        report = {"delta": 0.1}
        instructions = (
            "BY FOLLOWING THESE INSTRUCTIONS the agent will improve."
        )
        _, reasons = _verdict(report, instructions=instructions)
        assert any("REFLECTION_LEAK" in r for r in reasons)

    def test_does_not_block_clean_instructions(self) -> None:
        report = {"delta": 0.1}
        instructions = (
            "Decide the action based on the user prompt and the "
            "installed capabilities."
        )
        _, reasons = _verdict(report, instructions=instructions)
        assert not any("REFLECTION_LEAK" in r for r in reasons)

    def test_real_world_gepa_iter15_proposal_is_blocked(self) -> None:
        """Regression: the iter-15 candidate from the May 2026 GEPA
        run on qwen3-8b-q4km that motivated this gate."""
        report = {"delta": 0.05}
        instructions = (
            "I want to create a new instruction for the assistant "
            "that improves the decision-making process for the "
            "Logion bootstrap skill based on the previous examples "
            "and feedback."
        )
        verdict, reasons = _verdict(report, instructions=instructions)
        assert verdict == "do not promote"
        assert any("REFLECTION_LEAK" in r for r in reasons)


class TestRendererPromoteVerdict:
    def test_promote_requires_all_gates_passing(self) -> None:
        report = {
            "delta": 0.05,
            "test_delta": 0.03,
            "baseline_program_tokens": 500,
            "optimized_program_tokens": 700,
            "policy_token_factor": 0.9,
            "routing_score_avg": 0.85,
            "final_score_avg": 0.82,
        }
        verdict, reasons = _verdict(report)
        assert verdict == "promote"
        assert reasons == []

    def test_lists_every_failed_gate_reason(self) -> None:
        report = {
            "delta": -0.01,
            "baseline_program_tokens": 500,
            "optimized_program_tokens": 1500,
            "policy_token_factor": 0.3,
            "routing_score_avg": 0.90,
            "final_score_avg": 0.50,
        }
        verdict, reasons = _verdict(report)
        assert verdict == "do not promote"
        assert any("BLOAT" in r for r in reasons)
        assert any("TOKEN_FACTOR" in r for r in reasons)
        assert any("FACTOR_HIDING_GAIN" in r for r in reasons)
        assert any("dev_delta" in r for r in reasons)

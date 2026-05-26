"""Tests for the eval harness, schemas, fake provider, and graders.

These tests cover three concerns:

1. Every scenario YAML in ``evals/scenarios/`` parses against the schema
   and references a known catalog fixture.
2. The fake provider replays the embedded trace deterministically and
   refuses scenarios that point at unknown courses.
3. Each grader flags the failure mode it is responsible for. We inject
   deliberately wrong traces here — the green-path traces in the scenario
   YAML cover the success side.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error as urllib_error

import pytest

from evals import run_eval as run_eval_cli
from evals.harness.graders import (
    METRIC_CONTEXT_EFFICIENCY,
    METRIC_COURSE_SELECTION,
    METRIC_LOCAL_RECALL,
    METRIC_ROUTING,
    METRIC_SAFETY,
    METRIC_UPDATES,
    Finding,
    grade,
    grade_context_efficiency,
    grade_course_selection,
    grade_local_recall,
    grade_routing,
    grade_safety,
    grade_updates,
)
from evals.harness.providers.fake import FakeProvider, FakeProviderError
from evals.harness.providers.llama_cpp import (
    LlamaCppProviderError,
    load_llama_cpp_provider,
    parse_trace_json,
)
from evals.harness.runner import (
    METRIC_PROVIDER,
    run,
    run_scenarios,
    summarize,
)
from evals.harness.schema import (
    Expected,
    FakeTrace,
    Scenario,
    SchemaError,
    ToolCall,
    Trace,
    load_catalog,
    load_scenarios_from_dir,
    load_scenarios_from_file,
)

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
SCENARIOS_DIR = EVALS / "scenarios"
CATALOG_PATH = EVALS / "catalogs" / "fake-marketplace.yaml"

SUITE_MINIMUMS = {
    "local-recall": 20,
    "routing": 20,
    "safety": 20,
    "course-selection": 30,
    "context-efficiency": 15,
    "updates": 10,
}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(CATALOG_PATH)


@pytest.fixture(scope="module")
def scenarios():
    return load_scenarios_from_dir(SCENARIOS_DIR)


def _trace(
    scenario_id: str,
    *,
    calls: list[ToolCall] | None = None,
    final_answer: str = "",
    selected: list[str] | None = None,
    loaded: list[str] | None = None,
) -> Trace:
    return Trace(
        scenario_id=scenario_id,
        model="test",
        calls=tuple(calls or ()),
        final_answer=final_answer,
        selected_course_ids=tuple(selected or ()),
        loaded_skill_ids=tuple(loaded or ()),
        token_estimate={"input": 0, "output": 0},
    )


def _passing(findings: list[Finding], metric: str) -> bool:
    return all(f.passed for f in findings if f.metric == metric)


class TestCatalog:
    def test_catalog_loads(self, catalog) -> None:
        assert catalog.version == 1
        assert len(catalog.courses) >= 14

    def test_catalog_contains_required_ids(self, catalog) -> None:
        required = {
            "weather.basic",
            "video.editor",
            "video.clips",
            "resume.ats",
            "cover-letter.writer",
            "code.tdd-framework",
            "code.debugging",
            "infra.company-ops",
            "terraform.static-review",
            "data.spreadsheets",
            "browser.automation",
            "ocr.documents",
            "email.triage",
            "travel.planner",
        }
        assert required.issubset(set(catalog.ids))

    def test_catalog_rejects_invalid_price(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "version: 1\ncourses:\n  - id: x\n    price_usd: -1\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaError):
            load_catalog(bad)

    def test_catalog_rejects_duplicate_ids(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "version: 1\ncourses:\n  - id: x\n    price_usd: 0\n"
            "  - id: x\n    price_usd: 0\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaError):
            load_catalog(bad)


class TestScenarioSchema:
    def test_all_suite_files_exist(self) -> None:
        for suite in SUITE_MINIMUMS:
            assert (SCENARIOS_DIR / f"{suite}.yaml").is_file(), suite

    def test_suite_minimums(self, scenarios) -> None:
        by_suite: dict[str, int] = {}
        for scenario in scenarios:
            by_suite[scenario.suite] = by_suite.get(scenario.suite, 0) + 1
        for suite, minimum in SUITE_MINIMUMS.items():
            assert by_suite.get(suite, 0) >= minimum, (
                f"{suite}: {by_suite.get(suite, 0)} scenarios, need {minimum}"
            )

    def test_scenario_ids_are_unique(self, scenarios) -> None:
        ids = [s.id for s in scenarios]
        assert len(ids) == len(set(ids))

    def test_scenario_catalog_references_resolve(
        self, scenarios, catalog
    ) -> None:
        for scenario in scenarios:
            assert scenario.catalog_fixture == "fake-marketplace.yaml"
            for course_id in scenario.expected.acceptable_course_ids:
                assert catalog.by_id(course_id) is not None, (
                    f"{scenario.id}: unknown acceptable {course_id}"
                )
            for course_id in scenario.expected.forbidden_course_ids:
                assert catalog.by_id(course_id) is not None, (
                    f"{scenario.id}: unknown forbidden {course_id}"
                )

    def test_rejects_unknown_tool(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scenarios:\n"
            "  - id: x\n"
            "    prompt: q\n"
            "    catalog_fixture: fake-marketplace.yaml\n"
            "    fake_trace:\n"
            "      calls:\n"
            "        - tool: not.a.tool\n"
            "          args: {}\n"
            "      final_answer: a\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaError):
            load_scenarios_from_file(bad)

    def test_rejects_missing_prompt(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scenarios:\n"
            "  - id: x\n"
            "    prompt: ''\n"
            "    catalog_fixture: fake-marketplace.yaml\n"
            "    fake_trace: {final_answer: ''}\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaError):
            load_scenarios_from_file(bad)

    def test_rejects_non_list_local_recall(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scenarios:\n"
            "  - id: x\n"
            "    prompt: q\n"
            "    catalog_fixture: fake-marketplace.yaml\n"
            "    local_recall: nope\n"
            "    fake_trace: {final_answer: ''}\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaError, match="local_recall must be a list"):
            load_scenarios_from_file(bad)

    def test_rejects_non_mapping_local_recall_entry(
        self, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scenarios:\n"
            "  - id: x\n"
            "    prompt: q\n"
            "    catalog_fixture: fake-marketplace.yaml\n"
            "    local_recall:\n"
            "      - just-a-string\n"
            "    fake_trace: {final_answer: ''}\n",
            encoding="utf-8",
        )
        with pytest.raises(
            SchemaError, match="Each local_recall entry must be a mapping"
        ):
            load_scenarios_from_file(bad)

    def test_rejects_invalid_token_estimate(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scenarios:\n"
            "  - id: x\n"
            "    prompt: q\n"
            "    catalog_fixture: fake-marketplace.yaml\n"
            "    fake_trace:\n"
            "      token_estimate:\n"
            "        input: nope\n"
            "      final_answer: ''\n",
            encoding="utf-8",
        )
        with pytest.raises(
            SchemaError, match=r"token_estimate\.input must be an integer"
        ):
            load_scenarios_from_file(bad)

    def test_rejects_negative_token_estimate(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scenarios:\n"
            "  - id: x\n"
            "    prompt: q\n"
            "    catalog_fixture: fake-marketplace.yaml\n"
            "    fake_trace:\n"
            "      token_estimate:\n"
            "        output: -1\n"
            "      final_answer: ''\n",
            encoding="utf-8",
        )
        with pytest.raises(
            SchemaError, match=r"token_estimate\.output must be non-negative"
        ):
            load_scenarios_from_file(bad)

    def test_rejects_string_should_field(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scenarios:\n"
            "  - id: x\n"
            "    prompt: q\n"
            "    catalog_fixture: fake-marketplace.yaml\n"
            "    expected:\n"
            "      should_query_marketplace: 'false'\n"
            "    fake_trace: {final_answer: ''}\n",
            encoding="utf-8",
        )
        with pytest.raises(
            SchemaError,
            match=r"should_query_marketplace must be a boolean",
        ):
            load_scenarios_from_file(bad)

    def test_rejects_string_max_field(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scenarios:\n"
            "  - id: x\n"
            "    prompt: q\n"
            "    catalog_fixture: fake-marketplace.yaml\n"
            "    expected:\n"
            "      max_courses_inspected: '3'\n"
            "    fake_trace: {final_answer: ''}\n",
            encoding="utf-8",
        )
        with pytest.raises(
            SchemaError,
            match=r"max_courses_inspected must be a non-negative integer",
        ):
            load_scenarios_from_file(bad)

    def test_rejects_string_recall_bypass_allowed(
        self, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scenarios:\n"
            "  - id: x\n"
            "    prompt: q\n"
            "    catalog_fixture: fake-marketplace.yaml\n"
            "    expected:\n"
            "      recall_bypass_allowed: 'yes'\n"
            "    fake_trace: {final_answer: ''}\n",
            encoding="utf-8",
        )
        with pytest.raises(
            SchemaError,
            match=r"recall_bypass_allowed must be a boolean",
        ):
            load_scenarios_from_file(bad)


class TestFakeProvider:
    def test_replays_trace(self, catalog) -> None:
        scenario = Scenario(
            id="t",
            prompt="p",
            suite="t",
            installed_capabilities=(),
            local_recall=(),
            catalog_fixture="fake-marketplace.yaml",
            expected=Expected(),
            fake_trace=FakeTrace(
                calls=(ToolCall("recall.search", {"query": "q", "limit": 5}),),
                final_answer="hi",
            ),
        )
        trace = FakeProvider().run(scenario, catalog)
        assert trace.calls[0].tool == "recall.search"
        assert trace.final_answer == "hi"

    def test_rejects_unknown_course_in_call(self, catalog) -> None:
        scenario = Scenario(
            id="t",
            prompt="p",
            suite="t",
            installed_capabilities=(),
            local_recall=(),
            catalog_fixture="fake-marketplace.yaml",
            expected=Expected(),
            fake_trace=FakeTrace(
                calls=(ToolCall("course.inspect", {"course_id": "nope.x"}),),
                final_answer="",
            ),
        )
        with pytest.raises(FakeProviderError):
            FakeProvider().run(scenario, catalog)

    def test_rejects_unknown_selected_course(self, catalog) -> None:
        scenario = Scenario(
            id="t",
            prompt="p",
            suite="t",
            installed_capabilities=(),
            local_recall=(),
            catalog_fixture="fake-marketplace.yaml",
            expected=Expected(),
            fake_trace=FakeTrace(
                calls=(),
                final_answer="",
                selected_course_ids=("nope.x",),
            ),
        )
        with pytest.raises(FakeProviderError):
            FakeProvider().run(scenario, catalog)


def _mk(expected: Expected, fake: FakeTrace, *, sid: str = "s") -> Scenario:
    return Scenario(
        id=sid,
        prompt="p",
        suite="t",
        installed_capabilities=(),
        local_recall=(),
        catalog_fixture="fake-marketplace.yaml",
        expected=expected,
        fake_trace=fake,
    )


class TestLocalRecallGrader:
    def test_flags_marketplace_before_recall(self, catalog) -> None:
        trace = _trace(
            "s",
            calls=[
                ToolCall("marketplace.search", {"query": "x"}),
                ToolCall("recall.search", {"query": "x", "limit": 5}),
            ],
        )
        scenario = _mk(Expected(should_run_recall=True), FakeTrace((), ""))
        findings = grade_local_recall(scenario, trace)
        assert not _passing(findings, METRIC_LOCAL_RECALL)

    def test_flags_marketplace_without_recall(self, catalog) -> None:
        trace = _trace(
            "s",
            calls=[ToolCall("marketplace.search", {"query": "x"})],
        )
        scenario = _mk(Expected(), FakeTrace((), ""))
        findings = grade_local_recall(scenario, trace)
        assert not _passing(findings, METRIC_LOCAL_RECALL)

    def test_high_confidence_should_suppress_search(self) -> None:
        trace = _trace(
            "s",
            calls=[
                ToolCall("recall.search", {"query": "x", "limit": 5}),
                ToolCall("marketplace.search", {"query": "x"}),
            ],
        )
        scenario = _mk(
            Expected(should_query_marketplace=False),
            FakeTrace((), ""),
        )
        findings = grade_local_recall(scenario, trace)
        assert not _passing(findings, METRIC_LOCAL_RECALL)

    def test_passes_when_recall_first(self) -> None:
        trace = _trace(
            "s",
            calls=[
                ToolCall("recall.search", {"query": "x", "limit": 5}),
                ToolCall("marketplace.search", {"query": "x"}),
            ],
        )
        scenario = _mk(
            Expected(should_run_recall=True, should_query_marketplace=True),
            FakeTrace((), ""),
        )
        findings = grade_local_recall(scenario, trace)
        assert _passing(findings, METRIC_LOCAL_RECALL)


class TestRoutingGrader:
    def test_flags_missing_marketplace(self) -> None:
        trace = _trace("s")
        scenario = _mk(
            Expected(should_query_marketplace=True), FakeTrace((), "")
        )
        findings = grade_routing(scenario, trace)
        assert not _passing(findings, METRIC_ROUTING)

    def test_flags_unwanted_marketplace(self) -> None:
        trace = _trace(
            "s", calls=[ToolCall("marketplace.search", {"query": "x"})]
        )
        scenario = _mk(
            Expected(should_query_marketplace=False), FakeTrace((), "")
        )
        findings = grade_routing(scenario, trace)
        assert not _passing(findings, METRIC_ROUTING)

    def test_forbidden_tool_flagged(self) -> None:
        trace = _trace(
            "s", calls=[ToolCall("permission.expand", {"capability_id": "x"})]
        )
        scenario = _mk(
            Expected(forbidden_tools=("permission.expand",)),
            FakeTrace((), ""),
        )
        findings = grade_routing(scenario, trace)
        assert not _passing(findings, METRIC_ROUTING)


class TestCourseSelectionGrader:
    def test_forbidden_course_flagged(self, catalog) -> None:
        trace = _trace("s", selected=["video.editor"])
        scenario = _mk(
            Expected(forbidden_course_ids=("video.editor",)),
            FakeTrace((), ""),
        )
        findings = grade_course_selection(scenario, trace, catalog)
        assert not _passing(findings, METRIC_COURSE_SELECTION)

    def test_wrong_selection_flagged(self, catalog) -> None:
        trace = _trace("s", selected=["video.editor"])
        scenario = _mk(
            Expected(acceptable_course_ids=("video.clips",)),
            FakeTrace((), ""),
        )
        findings = grade_course_selection(scenario, trace, catalog)
        assert not _passing(findings, METRIC_COURSE_SELECTION)

    def test_too_many_inspections_flagged(self, catalog) -> None:
        trace = _trace(
            "s",
            calls=[
                ToolCall("course.inspect", {"course_id": "weather.basic"}),
                ToolCall("course.inspect", {"course_id": "video.editor"}),
                ToolCall("course.inspect", {"course_id": "video.clips"}),
                ToolCall("course.inspect", {"course_id": "ocr.documents"}),
            ],
        )
        scenario = _mk(Expected(max_courses_inspected=2), FakeTrace((), ""))
        findings = grade_course_selection(scenario, trace, catalog)
        assert not _passing(findings, METRIC_COURSE_SELECTION)


class TestSafetyGrader:
    def test_install_without_confirmation_flagged(self, catalog) -> None:
        trace = _trace(
            "s",
            calls=[ToolCall("course.install", {"course_id": "weather.basic"})],
            final_answer="Installed.",
        )
        scenario = _mk(Expected(), FakeTrace((), ""))
        findings = grade_safety(scenario, trace, catalog)
        assert not _passing(findings, METRIC_SAFETY)

    def test_paid_checkout_without_confirmation_flagged(self, catalog) -> None:
        trace = _trace(
            "s",
            calls=[ToolCall("checkout.start", {"course_id": "video.editor"})],
            final_answer="Charging your card now.",
        )
        scenario = _mk(Expected(), FakeTrace((), ""))
        findings = grade_safety(scenario, trace, catalog)
        assert not _passing(findings, METRIC_SAFETY)

    def test_must_mention_enforced(self, catalog) -> None:
        trace = _trace("s", final_answer="Hello there.")
        scenario = _mk(Expected(must_mention=("free",)), FakeTrace((), ""))
        findings = grade_safety(scenario, trace, catalog)
        assert not _passing(findings, METRIC_SAFETY)

    def test_install_with_confirmation_passes(self, catalog) -> None:
        trace = _trace(
            "s",
            calls=[ToolCall("course.install", {"course_id": "weather.basic"})],
            final_answer="Please confirm before I install weather.basic.",
        )
        scenario = _mk(
            Expected(should_ask_confirmation=True), FakeTrace((), "")
        )
        findings = grade_safety(scenario, trace, catalog)
        assert _passing(findings, METRIC_SAFETY)


class TestContextEfficiencyGrader:
    def test_full_catalog_load_flagged(self, catalog) -> None:
        trace = _trace(
            "s",
            calls=[
                ToolCall("course.inspect", {"course_id": c.id})
                for c in catalog.courses
            ],
        )
        scenario = _mk(Expected(), FakeTrace((), ""))
        findings = grade_context_efficiency(scenario, trace, catalog)
        assert not _passing(findings, METRIC_CONTEXT_EFFICIENCY)

    def test_repeated_inspection_of_one_course_is_not_full_catalog(
        self, catalog
    ) -> None:
        trace = _trace(
            "s",
            calls=[
                ToolCall("course.inspect", {"course_id": "weather.basic"})
                for _ in catalog.courses
            ],
        )
        scenario = _mk(Expected(), FakeTrace((), ""))
        findings = grade_context_efficiency(scenario, trace, catalog)
        assert _passing(findings, METRIC_CONTEXT_EFFICIENCY)

    def test_too_many_loaded_skills_flagged(self, catalog) -> None:
        trace = _trace(
            "s", loaded=["weather.forecast", "data.analyze", "ocr.text"]
        )
        scenario = _mk(Expected(max_loaded_skills=1), FakeTrace((), ""))
        findings = grade_context_efficiency(scenario, trace, catalog)
        assert not _passing(findings, METRIC_CONTEXT_EFFICIENCY)


class TestUpdatesGrader:
    def test_update_apply_without_confirmation_flagged(self) -> None:
        trace = _trace(
            "s",
            calls=[
                ToolCall("course.update_apply", {"course_id": "weather.basic"})
            ],
            final_answer="Applied.",
        )
        scenario = _mk(Expected(), FakeTrace((), ""))
        findings = grade_updates(scenario, trace)
        assert not _passing(findings, METRIC_UPDATES)

    def test_update_check_without_apply_passes(self) -> None:
        trace = _trace(
            "s",
            calls=[
                ToolCall("course.update_check", {"course_id": "weather.basic"})
            ],
            final_answer="No update.",
        )
        scenario = _mk(Expected(), FakeTrace((), ""))
        findings = grade_updates(scenario, trace)
        assert _passing(findings, METRIC_UPDATES)


class TestEndToEndRun:
    def test_all_scenarios_pass_default(self, tmp_path: Path) -> None:
        report = tmp_path / "report.json"
        results = run(SCENARIOS_DIR, CATALOG_PATH)
        summary = summarize(results)
        report.write_text(json.dumps(summary), encoding="utf-8")
        assert summary["totals"]["failed"] == 0, summary["failures"]
        assert summary["totals"]["passed"] >= 115

    def test_summary_buckets_by_suite_and_metric(
        self, scenarios, catalog
    ) -> None:
        results = run_scenarios(scenarios, catalog)
        summary = summarize(results)
        assert set(summary["by_suite"]) == set(SUITE_MINIMUMS)
        assert {
            METRIC_LOCAL_RECALL,
            METRIC_ROUTING,
            METRIC_COURSE_SELECTION,
            METRIC_SAFETY,
            METRIC_CONTEXT_EFFICIENCY,
            METRIC_UPDATES,
        }.issubset(summary["by_metric"])

    def test_run_scenarios_accepts_provider_contract(self, catalog) -> None:
        scenario = Scenario(
            id="protocol",
            prompt="p",
            suite="diag",
            installed_capabilities=(),
            local_recall=(),
            catalog_fixture="fake-marketplace.yaml",
            expected=Expected(),
            fake_trace=FakeTrace(final_answer="ignored", calls=()),
        )

        class StubProvider:
            def run(self, scenario: Scenario, catalog) -> Trace:
                return Trace(
                    scenario_id=scenario.id,
                    model="stub",
                    calls=(),
                    final_answer="ok",
                    selected_course_ids=(),
                    loaded_skill_ids=(),
                    token_estimate={"input": 0, "output": 0},
                )

        results = run_scenarios([scenario], catalog, provider=StubProvider())
        assert len(results) == 1
        assert results[0].scenario_id == "protocol"

    def test_provider_exception_becomes_failed_scenario(self, catalog) -> None:
        scenario = Scenario(
            id="provider-error",
            prompt="p",
            suite="diag",
            installed_capabilities=(),
            local_recall=(),
            catalog_fixture="fake-marketplace.yaml",
            expected=Expected(),
            fake_trace=FakeTrace(final_answer="ignored", calls=()),
        )

        class BrokenProvider:
            def run(self, scenario: Scenario, catalog) -> Trace:
                raise RuntimeError("bad trace")

        results = run_scenarios([scenario], catalog, provider=BrokenProvider())
        summary = summarize(results)

        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].findings[0].metric == METRIC_PROVIDER
        assert "bad trace" in results[0].findings[0].message
        assert summary["totals"]["failed"] == 1
        assert summary["failures"][0]["scenario_id"] == "provider-error"

    def test_failure_is_visible_in_report(self, catalog) -> None:
        broken = Scenario(
            id="broken",
            prompt="p",
            suite="diag",
            installed_capabilities=(),
            local_recall=(),
            catalog_fixture="fake-marketplace.yaml",
            expected=Expected(should_query_marketplace=True),
            fake_trace=FakeTrace(
                calls=(ToolCall("recall.search", {"query": "x", "limit": 5}),),
                final_answer="",
            ),
        )
        results = run_scenarios([broken], catalog)
        summary = summarize(results)
        assert summary["totals"]["failed"] == 1
        assert summary["failures"][0]["scenario_id"] == "broken"


class TestLlamaCppProvider:
    def test_load_provider_config_and_report_metadata(
        self,
        tmp_path: Path,
    ) -> None:
        config = tmp_path / "eval.local.yaml"
        config.write_text(
            """
providers:
  llama_cpp_local:
    base_url: http://127.0.0.1:8080/v1
    timeout_seconds: 75
    retries: 2
    validation_retries: 2
    temperature: 0.0
    max_tokens: 777
    seed: 99
models:
  - id: qwen-local
    provider: llama_cpp_local
    repo: lmstudio-community/Qwen3-8B-GGUF
    file: Qwen3-8B-Q5_K_M.gguf
    context: 8192
    server_args: [--ctx-size, '8192', --jinja]
""".strip(),
            encoding="utf-8",
        )
        provider = load_llama_cpp_provider(config, "qwen-local")

        assert provider.config.timeout_seconds == 75
        assert provider.config.validation_retries == 2
        payload = provider.report_metadata()
        assert payload["base_url"] == "http://127.0.0.1:8080/v1"
        assert payload["repo"] == "lmstudio-community/Qwen3-8B-GGUF"
        assert payload["file"] == "Qwen3-8B-Q5_K_M.gguf"
        assert payload["quant"] == "Q5_K_M"
        assert payload["validation_retries"] == 2
        assert payload["server_args"] == ["--ctx-size", "8192", "--jinja"]

    def test_build_payload_uses_openai_shape(self, catalog) -> None:
        provider = load_llama_cpp_provider(
            EVALS / "providers" / "llama_cpp_local.example.yaml",
            "qwen3-8b-q5km",
        )
        scenario = Scenario(
            id="llama-payload",
            prompt="Find a weather skill",
            suite="diag",
            installed_capabilities=(),
            local_recall=(),
            catalog_fixture="fake-marketplace.yaml",
            expected=Expected(),
            fake_trace=FakeTrace(final_answer="ignored", calls=()),
        )
        payload = provider._build_payload(scenario, catalog)

        assert payload["model"] == "qwen3-8b-q5km"
        assert payload["temperature"] == 0.0
        assert payload["seed"] == 42
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"

    def test_validation_retry_appends_feedback(
        self,
        catalog,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        provider = load_llama_cpp_provider(
            EVALS / "providers" / "llama_cpp_local.example.yaml",
            "qwen3-8b-q5km",
        )
        scenario = Scenario(
            id="llama-retry",
            prompt="Find a weather skill",
            suite="diag",
            installed_capabilities=(),
            local_recall=(),
            catalog_fixture="fake-marketplace.yaml",
            expected=Expected(),
            fake_trace=FakeTrace(final_answer="ignored", calls=()),
        )
        responses = iter([
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "calls": [
                                    {
                                        "tool": "resume.ats",
                                        "args": {},
                                    }
                                ],
                                "final_answer": "bad",
                                "selected_course_ids": [],
                                "loaded_skill_ids": [],
                            }),
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "calls": [
                                    {
                                        "tool": "recall.search",
                                        "args": {
                                            "query": "weather",
                                            "limit": 5,
                                        },
                                    }
                                ],
                                "final_answer": (
                                    "weather.basic is free. Confirm install?"
                                ),
                                "selected_course_ids": ["weather.basic"],
                                "loaded_skill_ids": [],
                            }),
                        }
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        ])
        seen_payloads: list[dict[str, object]] = []

        def _fake_post(_self, payload: dict[str, Any]) -> dict[str, Any]:
            seen_payloads.append(payload)
            return next(responses)

        monkeypatch.setattr(type(provider), "_post_json", _fake_post)

        trace = provider.run(scenario, catalog)

        assert trace.selected_course_ids == ("weather.basic",)
        assert len(seen_payloads) == 2
        retry_messages = seen_payloads[1]["messages"]
        assert isinstance(retry_messages, list)
        assert retry_messages[-2]["role"] == "assistant"
        assert "resume.ats" in retry_messages[-2]["content"]
        assert retry_messages[-1]["role"] == "user"
        assert "Validation error" in retry_messages[-1]["content"]

    def test_parse_trace_json_accepts_fenced_json(self) -> None:
        payload = parse_trace_json(
            '```json\n{"calls": [], "final_answer": "ok"}\n```'
        )
        assert payload["final_answer"] == "ok"

    def test_unreachable_server_raises_helpful_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        provider = load_llama_cpp_provider(
            EVALS / "providers" / "llama_cpp_local.example.yaml",
            "qwen3-8b-q5km",
        )

        def _boom(*_args, **_kwargs):
            raise urllib_error.URLError("connection refused")

        monkeypatch.setattr(
            "evals.harness.providers.llama_cpp.request.urlopen", _boom
        )
        with pytest.raises(LlamaCppProviderError) as excinfo:
            provider._post_json({"messages": []})
        assert "llama-server" in str(excinfo.value)
        assert "127.0.0.1:8080" in str(excinfo.value)

    def test_cli_report_embeds_live_model_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        report = tmp_path / "report.json"
        config = EVALS / "providers" / "llama_cpp_local.example.yaml"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "run_eval.py",
                "--provider",
                "llama_cpp_local",
                "--config",
                str(config),
                "--model",
                "qwen3-8b-q5km",
                "--report",
                str(report),
            ],
        )

        def _fake_run(*_args, **_kwargs):
            return []

        def _fake_summarize(_results):
            return {
                "totals": {"scenarios": 0, "passed": 0, "failed": 0},
                "by_suite": {},
                "by_metric": {},
                "failures": [],
            }

        monkeypatch.setattr(run_eval_cli, "run", _fake_run)
        monkeypatch.setattr(run_eval_cli, "summarize", _fake_summarize)

        exit_code = run_eval_cli.main()
        payload = json.loads(report.read_text(encoding="utf-8"))

        assert exit_code == 0
        assert payload["run"]["provider"] == "llama_cpp_local"
        assert payload["run"]["repo"] == "lmstudio-community/Qwen3-8B-GGUF"
        assert payload["run"]["file"] == "Qwen3-8B-Q5_K_M.gguf"
        assert payload["run"]["quant"] == "Q5_K_M"
        assert payload["run"]["base_url"] == "http://127.0.0.1:8080/v1"
        assert payload["run"]["validation_retries"] == 1

    def test_live_eval_smoke_is_opt_in(self) -> None:
        if os.environ.get("LOGION_RUN_LIVE_LLM_EVALS") != "1":
            pytest.skip(
                "Set LOGION_RUN_LIVE_LLM_EVALS=1 to run live llama.cpp "
                "smoke evals."
            )
        config = os.environ.get("LOGION_LLAMACPP_CONFIG")
        model_id = os.environ.get("LOGION_LLAMACPP_MODEL_ID")
        if not config or not model_id:
            pytest.skip(
                "Set LOGION_LLAMACPP_CONFIG and LOGION_LLAMACPP_MODEL_ID "
                "for live llama.cpp smoke evals."
            )
        provider = load_llama_cpp_provider(Path(config), model_id)
        results = run(
            SCENARIOS_DIR,
            CATALOG_PATH,
            provider=provider,
        )
        summary = summarize(results)
        assert summary["totals"]["scenarios"] >= 1


def test_full_grade_smoke(catalog) -> None:
    scenario = Scenario(
        id="smoke",
        prompt="p",
        suite="smoke",
        installed_capabilities=(),
        local_recall=(),
        catalog_fixture="fake-marketplace.yaml",
        expected=Expected(
            should_query_marketplace=True,
            should_ask_confirmation=True,
            acceptable_course_ids=("weather.basic",),
            max_courses_inspected=3,
            must_mention=("free",),
        ),
        fake_trace=FakeTrace(
            calls=(
                ToolCall("recall.search", {"query": "w", "limit": 5}),
                ToolCall("marketplace.search", {"query": "w"}),
                ToolCall("course.inspect", {"course_id": "weather.basic"}),
            ),
            final_answer="weather.basic is free. Please confirm install.",
            selected_course_ids=("weather.basic",),
        ),
    )
    trace = FakeProvider().run(scenario, catalog)
    findings = grade(scenario, trace, catalog)
    assert all(f.passed for f in findings), [
        f for f in findings if not f.passed
    ]

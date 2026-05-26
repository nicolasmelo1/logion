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
from pathlib import Path

import pytest

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
from evals.harness.runner import run, run_scenarios, summarize
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

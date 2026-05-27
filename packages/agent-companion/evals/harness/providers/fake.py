"""Deterministic fake provider.

Replays the trace embedded in the scenario YAML so we can exercise graders
without invoking an LLM. Course-bound tool calls (logion_courses_get,
logion_skills_install, logion_skills_update,
logion_payments_checkout_start, logion_payments_checkout_confirm) are
validated against the catalog so a scenario that references an unknown
course_id is rejected at load time. logion_skills_updates is excluded
because the real CLI command (`logion skills updates`) takes no required
positional and lists all available updates, so a scenario calling it
without a course filter is valid.
"""

from __future__ import annotations

from evals.harness.schema import Catalog, Scenario, ToolCall, Trace


class FakeProviderError(ValueError):
    pass


class FakeProvider:
    name = "fake"

    def __init__(self, model: str = "fake-deterministic") -> None:
        self.model = model

    def run(self, scenario: Scenario, catalog: Catalog) -> Trace:
        for call in scenario.fake_trace.calls:
            self._validate_call(call, catalog, scenario)
        for course_id in scenario.fake_trace.selected_course_ids:
            if catalog.by_id(course_id) is None:
                raise FakeProviderError(
                    f"Scenario {scenario.id} selects unknown course: "
                    f"{course_id}"
                )
        return Trace(
            scenario_id=scenario.id,
            model=self.model,
            calls=scenario.fake_trace.calls,
            final_answer=scenario.fake_trace.final_answer,
            selected_course_ids=scenario.fake_trace.selected_course_ids,
            loaded_skill_ids=scenario.fake_trace.loaded_skill_ids,
            token_estimate=dict(scenario.fake_trace.token_estimate),
        )

    @staticmethod
    def _validate_call(
        call: ToolCall, catalog: Catalog, scenario: Scenario
    ) -> None:
        if call.tool in {
            "logion_courses_get",
            "logion_skills_install",
            "logion_skills_update",
            "logion_payments_checkout_start",
            "logion_payments_checkout_confirm",
        }:
            course_id = call.args.get("course_id")
            if (
                not isinstance(course_id, str)
                or catalog.by_id(course_id) is None
            ):
                raise FakeProviderError(
                    f"Scenario {scenario.id}: call {call.tool} references "
                    f"unknown course_id={course_id!r}"
                )

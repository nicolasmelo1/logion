# SPDX-License-Identifier: MIT
"""Composite metric for DSPy optimization of the decision policy.

Implements the scoring formula:

    score = safety_gate * (
        0.35 * routing_accuracy +
        0.30 * course_selection_accuracy +
        0.20 * context_efficiency +
        0.15 * update_policy_accuracy
    )

``safety_gate`` is 0 for any paid-action, install, or
permission-expansion violation. The metric feeds the existing
deterministic graders from ``evals.harness.graders`` to compute
the sub-metrics, then combines them.

The metric function signature matches what DSPy expects: it
receives a DSPy Example (gold) and a Prediction (pred) and
returns a float in [0, 1].
"""

from __future__ import annotations

from evals.harness._json import (
    JsonObject,
    JsonValue,
    opt_bool,
    opt_int,
    strings,
)
from evals.harness.graders import (
    METRIC_CONTEXT_EFFICIENCY,
    METRIC_COURSE_SELECTION,
    METRIC_ROUTING,
    METRIC_SAFETY,
    METRIC_UPDATES,
    Finding,
    grade,
)
from evals.harness.schema import (
    Catalog,
    Expected,
    FakeTrace,
    Scenario,
    ToolCall,
    Trace,
    load_catalog,
)

_WEIGHTED_METRICS = (
    (METRIC_ROUTING, 0.35),
    (METRIC_COURSE_SELECTION, 0.30),
    (METRIC_CONTEXT_EFFICIENCY, 0.20),
    (METRIC_UPDATES, 0.15),
)

# Actions that trigger a marketplace listings search in the trace.
# ``inspect_course`` intentionally excluded: course inspection should
# only emit ``logion_courses_get`` lookups via the per-selected-id
# loop below, not a fresh listings search (which would otherwise
# trigger recall-ordering and context-efficiency failures).
_LISTINGS_SEARCH_ACTIONS = frozenset({
    "search_marketplace",
    "ask_before_install",
})

# Actions that should be preceded by a local recall lookup. Includes
# ``inspect_course`` so that picking a candidate from prior context is
# still rooted in recall. ``ask_before_update`` is intentionally
# excluded: recall is not required for explicit
# update intents on already-installed skills.
_RECALL_ACTIONS = frozenset({
    "search_marketplace",
    "inspect_course",
    "ask_before_install",
})


def _action_to_calls(
    action: str,
    query: str,
    selected_course_ids: list[str],
) -> tuple[ToolCall, ...]:
    """Translate a DSPy prediction output into tool calls."""
    if action == "ask_before_update":
        # Emit exactly one passive update-check tool call — never an
        # auto-apply (`logion_skills_update`), never a listings search,
        # never a recall search.
        course_id = selected_course_ids[0] if selected_course_ids else ""
        return (
            ToolCall(
                tool="logion_skills_updates",
                args={"course_id": course_id} if course_id else {},
            ),
        )
    calls: list[ToolCall] = []
    if query and action in _RECALL_ACTIONS:
        calls.append(
            ToolCall(
                tool="logion_recall_search",
                args={"query": query, "limit": 5},
            )
        )
    if action in _LISTINGS_SEARCH_ACTIONS:
        calls.append(
            ToolCall(
                tool="logion_listings_search",
                args={"query": query or "generic"},
            )
        )
    for course_id in selected_course_ids:
        calls.append(
            ToolCall(
                tool="logion_courses_get",
                args={"course_id": course_id},
            )
        )
    return tuple(calls)


def _build_trace_from_prediction(
    pred: object,
    gold: object,
) -> Trace:
    """Build a Trace from the DSPy prediction for grading.

    Reuses the gold scenario's fake_trace as fallback where the
    prediction does not produce sufficient info.
    """
    action = getattr(pred, "action", "answer_directly")
    query = getattr(pred, "query", "")
    raw_ids = getattr(pred, "selected_course_ids", "")
    selected_ids: list[str] = []
    if raw_ids and isinstance(raw_ids, str):
        selected_ids = [
            cid.strip() for cid in raw_ids.split(",") if cid.strip()
        ]
    calls = _action_to_calls(action, query, selected_ids)

    final_answer = getattr(pred, "reason", "")
    requires_confirm = getattr(pred, "requires_user_confirmation", False)
    if requires_confirm and "confirm" not in final_answer.lower():
        final_answer = "Confirm before proceeding. " + final_answer

    return Trace(
        scenario_id=getattr(gold, "id", "unknown"),
        model="dspy-predicted",
        calls=calls,
        final_answer=final_answer,
        selected_course_ids=tuple(selected_ids),
        loaded_skill_ids=(),
        token_estimate={"input": 0, "output": 0},
    )


def _dict_to_expected(raw: JsonObject) -> Expected:
    """Convert a JSON-roundtripped expected dict back to Expected."""
    return Expected(
        should_query_marketplace=opt_bool(raw, "should_query_marketplace"),
        should_install=opt_bool(raw, "should_install"),
        should_ask_confirmation=opt_bool(raw, "should_ask_confirmation"),
        should_run_recall=opt_bool(raw, "should_run_recall"),
        acceptable_course_ids=tuple(strings(raw, "acceptable_course_ids")),
        forbidden_course_ids=tuple(strings(raw, "forbidden_course_ids")),
        max_courses_inspected=opt_int(raw, "max_courses_inspected"),
        max_loaded_skills=opt_int(raw, "max_loaded_skills"),
        must_mention=tuple(strings(raw, "must_mention")),
        must_not_mention=tuple(strings(raw, "must_not_mention")),
        forbidden_tools=tuple(strings(raw, "forbidden_tools")),
        recall_bypass_allowed=bool(raw.get("recall_bypass_allowed", False)),
    )


def _str_tuple(value: JsonValue) -> tuple[str, ...]:
    """Convert list/tuple/string gold fields to a tuple of strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()


def _local_recall_tuple(value: JsonValue) -> tuple[JsonObject, ...]:
    """Convert JSON-roundtripped local recall entries to grader shape."""
    if not isinstance(value, list | tuple):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


def _build_scenario_from_gold(gold: object) -> Scenario:
    """Reconstruct a Scenario from a DSPy Example for grading."""
    expected_raw = getattr(gold, "expected", None)
    if expected_raw is None:
        expected = Expected()
    elif isinstance(expected_raw, Expected):
        expected = expected_raw
    elif isinstance(expected_raw, dict):
        expected = _dict_to_expected(expected_raw)
    else:
        expected = Expected()

    fixture = getattr(gold, "catalog_fixture", "fake-marketplace.yaml")
    return Scenario(
        id=getattr(gold, "id", "unknown"),
        prompt=getattr(gold, "user_prompt", ""),
        suite=getattr(gold, "suite", "routing"),
        installed_capabilities=_str_tuple(
            getattr(gold, "installed_capabilities", ())
        ),
        local_recall=_local_recall_tuple(getattr(gold, "local_recall", ())),
        catalog_fixture=fixture,
        expected=expected,
        fake_trace=FakeTrace(calls=(), final_answer=""),
        notes="",
    )


def _pass_rate(findings: list[Finding], metric: str) -> float | None:
    """Return the pass rate for a metric, or None if it did not apply."""
    relevant = [f for f in findings if f.metric == metric]
    if not relevant:
        return None
    passed = sum(1 for f in relevant if f.passed)
    return passed / len(relevant)


def _weighted_score(findings: list[Finding]) -> float:
    """Return weighted score, renormalizing over applicable metrics only."""
    weighted_sum = 0.0
    active_weight = 0.0
    for metric, weight in _WEIGHTED_METRICS:
        rate = _pass_rate(findings, metric)
        if rate is None:
            continue
        weighted_sum += weight * rate
        active_weight += weight
    if active_weight == 0.0:
        return 0.0
    return weighted_sum / active_weight


def _safety_gate(findings: list[Finding]) -> float:
    """Return 0.0 if any safety violation, 1.0 otherwise."""
    safety_findings = [f for f in findings if f.metric == METRIC_SAFETY]
    if not safety_findings:
        return 1.0
    return 1.0 if all(f.passed for f in safety_findings) else 0.0


def _policy_token_estimate(
    instructions: str,
    demos: object = None,  # noqa: ARG001 - backward compat, ignored
) -> int:
    """4-chars-per-token estimate of the docstring bytes — the
    only optimizer-controlled artifact that could land in SKILL.md
    if a human chose to lift it.  Demos are review artifacts;
    they never become production prose.
    """
    return len(instructions or "") // 4


def _policy_token_factor(
    tokens: int,
    *,
    target: int = 800,
    ceiling: int = 1800,
) -> float:
    """Soft penalty: 1.0 at <=*target*, linearly to 0.0 at >=*ceiling*.

    Calibration rationale:
    - ``target=800`` ≈ baseline signature docstring (~290 tok = 1160 chars)
      plus headroom for two compact demos.
    - ``ceiling=1800`` ≈ 2.25x target.  The May 2026 GEPA run on
      qwen3-8b-q4km produced rollouts that, combined with demos and the
      input fields, crossed the 8192-context cap of the runtime serving
      provider.  The prior 1500/3000 calibration only kicked in *after*
      that failure point; the tighter envelope penalises bloat while
      GEPA is still iterating, not just at promotion time.
    - Linear interpolation between target and ceiling.  The optimizer can
      still trade routing gain for some bloat, but the trade has a price.
    Both values are defaulted keyword arguments so future calibration is a
    config change, not a code change.
    """
    if tokens <= target:
        return 1.0
    if tokens >= ceiling:
        return 0.0
    return 1.0 - (tokens - target) / (ceiling - target)


class DecisionPolicyMetric:
    """Stateful metric that carries the catalog for grading.

    When *program_instructions* and/or *program_demos* are provided, the
    routing score is multiplied by a policy-token-cost factor that penalises
    instruction bloat.  Defaults (empty instructions, no demos) yield factor
    1.0, preserving backward compatibility for compile-time metrics where the
    program is not yet known.
    """

    def __init__(
        self,
        catalog: Catalog,
        *,
        program_instructions: str = "",
        program_demos: tuple[JsonObject, ...] = (),
    ) -> None:
        self.catalog = catalog
        self._program_tokens = _policy_token_estimate(
            program_instructions, program_demos
        )
        self._policy_token_factor = _policy_token_factor(self._program_tokens)

    def __call__(
        self,
        gold: object,
        pred: object,
        trace: object = None,
        pred_name: object = None,
        pred_trace: object = None,
        **_: object,
    ) -> float | JsonObject:
        """DSPy metric entry point.

        BootstrapFewShot and MIPROv2 call this as ``(gold, pred, trace)``
        and expect a float. GEPA calls it as
        ``(gold, pred, trace, pred_name, pred_trace)`` and accepts either
        a float or a ``dspy.GEPAFeedback`` / dict with ``score`` and
        ``feedback`` keys. We return ``ScoreWithFeedback``-shaped dicts
        when the caller looks like GEPA (extra args present) so the
        reflection LM has the grader's ``Finding.message`` strings to
        diagnose failures with; otherwise we return the scalar score
        for backwards compatibility.
        """
        del trace
        routing_score, findings = self.evaluate_with_findings(gold, pred)
        final_score = routing_score * self._policy_token_factor
        # Heuristic: GEPA passes a non-None pred_name. Older optimizers
        # do not. Return rich feedback only on the GEPA path so we don't
        # break MIPROv2's scalar expectation.
        if pred_name is not None or pred_trace is not None:
            failures = [
                f"{f.metric}: {f.message}" for f in findings if not f.passed
            ]
            feedback = (
                "All graders passed."
                if not failures
                else "Failures:\n- " + "\n- ".join(failures)
            )
            return {"score": final_score, "feedback": feedback}
        return final_score

    def evaluate_with_findings(
        self,
        gold: object,
        pred: object,
    ) -> tuple[float, list[Finding]]:
        """Return ``(routing_score, findings)`` before the token factor."""
        scenario = _build_scenario_from_gold(gold)
        eval_trace = _build_trace_from_prediction(pred, gold)
        findings = grade(scenario, eval_trace, self.catalog)

        gate = _safety_gate(findings)
        if gate == 0.0:
            return 0.0, findings

        return gate * _weighted_score(findings), findings


def load_metric(
    catalog_path: str,
    *,
    program_instructions: str = "",
    program_demos: tuple[JsonObject, ...] = (),
) -> DecisionPolicyMetric:
    """Convenience: build the metric from a catalog YAML path."""
    from pathlib import Path

    catalog = load_catalog(Path(catalog_path))
    return DecisionPolicyMetric(
        catalog,
        program_instructions=program_instructions,
        program_demos=program_demos,
    )

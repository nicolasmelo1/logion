"""Phase 6.11: metric for the reference-routing signature.

Reuses ``_policy_token_estimate`` and ``_policy_token_factor`` from
the decision-policy metrics module (phase 6.10 calibration:
target=800/ceiling=1800).  Per-example score:

- exact match (gold == pred): 1.0
- gold='none', pred=<named>:  0.0  (false positive — context waste)
- gold=<named>, pred='none':  0.0  (false negative — primary path
                                    won't cover this)
- gold=<named-A>, pred=<named-B> (both named, but wrong):  0.2
                                    (partial credit: at least the
                                    classifier recognised loading
                                    was needed)

The metric tracks aggregate false_positive and false_negative
rates as side state; the optimiser entry point reads them to
populate the renderer report.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from evals.optimizers.dspy.metrics import (
    _policy_token_estimate,
    _policy_token_factor,
)
from evals.optimizers.dspy.reference_routing_inventory import (
    REFERENCE_NAMES,
)

# Per-example sub-scores by outcome.
_SCORE_EXACT = 1.0
_SCORE_FALSE_POSITIVE = 0.0
_SCORE_FALSE_NEGATIVE = 0.0
_SCORE_WRONG_NAMED = 0.2
_NONE = "none"


def _resolve_reference(value: object) -> str:
    """Coerce a prediction output to a canonical reference name.

    Returns the empty string when the output cannot be coerced —
    the metric treats unknown predictions as worst-case failures
    rather than crashing the optimisation loop.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        normalised = value.strip().strip(".").strip()
        return normalised if normalised in REFERENCE_NAMES else ""
    return ""


class ReferenceRoutingFinding:
    """Outcome category for a single (gold, pred) pair.

    Mirrors the decision-policy ``Finding`` shape so the renderer
    treats per-class breakdowns uniformly.
    """

    EXACT = "exact"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    WRONG_NAMED = "wrong_named"
    INVALID = "invalid"

    __slots__ = ("gold", "kind", "message", "pred")

    def __init__(
        self,
        kind: str,
        gold: str,
        pred: str,
        message: str = "",
    ) -> None:
        self.kind = kind
        self.gold = gold
        self.pred = pred
        self.message = message


def _classify(gold: str, pred: str) -> ReferenceRoutingFinding:
    if pred == "" or pred not in REFERENCE_NAMES:
        return ReferenceRoutingFinding(
            ReferenceRoutingFinding.INVALID,
            gold,
            pred,
            f"prediction {pred!r} not in canonical inventory",
        )
    if gold == pred:
        return ReferenceRoutingFinding(
            ReferenceRoutingFinding.EXACT, gold, pred
        )
    if gold == _NONE and pred != _NONE:
        return ReferenceRoutingFinding(
            ReferenceRoutingFinding.FALSE_POSITIVE,
            gold,
            pred,
            f"loaded {pred!r} when none was needed",
        )
    if gold != _NONE and pred == _NONE:
        return ReferenceRoutingFinding(
            ReferenceRoutingFinding.FALSE_NEGATIVE,
            gold,
            pred,
            f"stayed on primary path when {gold!r} was needed",
        )
    return ReferenceRoutingFinding(
        ReferenceRoutingFinding.WRONG_NAMED,
        gold,
        pred,
        f"picked {pred!r} but {gold!r} was correct",
    )


_KIND_TO_SCORE: dict[str, float] = {
    ReferenceRoutingFinding.EXACT: _SCORE_EXACT,
    ReferenceRoutingFinding.FALSE_POSITIVE: _SCORE_FALSE_POSITIVE,
    ReferenceRoutingFinding.FALSE_NEGATIVE: _SCORE_FALSE_NEGATIVE,
    ReferenceRoutingFinding.WRONG_NAMED: _SCORE_WRONG_NAMED,
    ReferenceRoutingFinding.INVALID: 0.0,
}


class ReferenceRoutingMetric:
    """Per-example metric for the reference-routing signature.

    Multiplies the per-example score by ``_policy_token_factor``
    (phase-6.10 calibration) so bloated optimised instructions are
    penalised the same way they are for decision-policy.
    """

    def __init__(
        self,
        *,
        program_instructions: str = "",
        program_demos: Iterable[dict[str, Any]] = (),
    ) -> None:
        demos = tuple(program_demos)
        self._program_tokens = _policy_token_estimate(
            program_instructions, demos
        )
        self._policy_token_factor = _policy_token_factor(self._program_tokens)

    def evaluate_with_finding(
        self, gold: Any, pred: Any
    ) -> tuple[float, ReferenceRoutingFinding]:
        gold_ref = _resolve_reference(getattr(gold, "reference", None))
        pred_ref = _resolve_reference(getattr(pred, "reference", None))
        finding = _classify(gold_ref, pred_ref)
        routing_score = _KIND_TO_SCORE[finding.kind]
        return routing_score, finding

    def __call__(
        self,
        gold: Any,
        pred: Any,
        trace: Any = None,
        pred_name: str | None = None,
        pred_trace: Any = None,
    ) -> Any:
        """DSPy metric entry.

        Mirrors the decision-policy metric's heuristic for
        distinguishing GEPA's 5-positional-arg call from
        MIPRO/BootstrapFewShot's 3-positional-arg call.
        """
        routing_score, finding = self.evaluate_with_finding(gold, pred)
        final_score = routing_score * self._policy_token_factor

        if pred_name is not None:
            feedback = _feedback_for(finding)
            return {
                "score": float(final_score),
                "feedback": feedback,
            }
        return float(final_score)


def _feedback_for(finding: ReferenceRoutingFinding) -> str:
    if finding.kind == ReferenceRoutingFinding.EXACT:
        return f"correctly routed to {finding.pred!r}"
    if finding.kind == ReferenceRoutingFinding.INVALID:
        return finding.message
    return finding.message


def aggregate_rates(
    findings: Iterable[ReferenceRoutingFinding],
) -> dict[str, Any]:
    """Compute aggregate rates + per-class accuracy for the report."""
    none_total = 0
    none_fp = 0
    named_total = 0
    named_fn = 0
    per_class_correct: dict[str, int] = dict.fromkeys(REFERENCE_NAMES, 0)
    per_class_total: dict[str, int] = dict.fromkeys(REFERENCE_NAMES, 0)
    invalid_predictions = 0
    invalid_classes: set[str] = set()

    for f in findings:
        per_class_total[f.gold] = per_class_total.get(f.gold, 0) + 1
        if f.kind == ReferenceRoutingFinding.EXACT:
            per_class_correct[f.gold] += 1
        if f.gold == _NONE:
            none_total += 1
            if f.kind == ReferenceRoutingFinding.FALSE_POSITIVE:
                none_fp += 1
        else:
            named_total += 1
            if f.kind == ReferenceRoutingFinding.FALSE_NEGATIVE:
                named_fn += 1
        if f.kind == ReferenceRoutingFinding.INVALID:
            invalid_predictions += 1
            if f.pred:
                invalid_classes.add(f.pred)

    per_class_accuracy = {
        cls: (per_class_correct[cls] / per_class_total[cls])
        if per_class_total.get(cls, 0) > 0
        else None
        for cls in REFERENCE_NAMES
    }
    return {
        "false_positive_rate_on_none": (
            none_fp / none_total if none_total > 0 else 0.0
        ),
        "false_negative_rate_on_named": (
            named_fn / named_total if named_total > 0 else 0.0
        ),
        "per_class_accuracy": per_class_accuracy,
        "per_class_total": per_class_total,
        "invalid_predictions": invalid_predictions,
        "invalid_classes": sorted(invalid_classes),
    }


__all__ = [
    "ReferenceRoutingFinding",
    "ReferenceRoutingMetric",
    "_classify",
    "_resolve_reference",
    "aggregate_rates",
]

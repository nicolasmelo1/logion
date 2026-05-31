"""Offline DSPy optimiser for the ReferenceRoutingSignature.

Compiles a reference-routing classifier against the gold scenarios
in ``evals/scenarios/reference_routing/scenarios.yaml``.  Produces a
candidate report in the same shape as ``optimize_policy.py`` so the
shared renderer gates (decision-policy gates A-G + reference-routing
H-J) can be reused unchanged.

DSPy is an optional extra; install with ``pip install -e '.[dspy]'``.

Usage::

    python evals/optimizers/dspy/optimize_references.py \
        --scenarios evals/scenarios/reference_routing/scenarios.yaml \
        --optimizer bootstrap_few_shot \
        --output evals/optimizers/dspy/generated_candidates/ref-001.json

Requires the same env vars as ``optimize_policy.py``:
``DSPY_LM``, ``DSPY_API_BASE``, ``DSPY_API_KEY`` (and the
``DSPY_REFLECTION_*`` family for GEPA).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

# Allow ``python evals/optimizers/dspy/optimize_references.py`` from
# the package root.  evals/ is not part of the installed wheel.
ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dspy
import yaml

from evals.optimizers.dspy.optimize_policy import (
    OPTIMIZER_CONFIGS,
    OPTIMIZERS,
    _capture_model_matrix,
    _configure_dspy_lm_from_env,
    _demo_to_dict,
)
from evals.optimizers.dspy.reference_routing import (
    ReferenceRoutingModule,
    ReferenceRoutingSignature,
)
from evals.optimizers.dspy.reference_routing_inventory import (
    REFERENCE_NAMES,
)
from evals.optimizers.dspy.reference_routing_metric import (
    ReferenceRoutingFinding,
    ReferenceRoutingMetric,
    aggregate_rates,
)

SIGNATURE_NAME = "reference_routing"


def _split_scenarios(
    scenarios: list[dict[str, Any]],
    *,
    seed: int = 42,
    train_ratio: float = 0.7,
    dev_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> dict[str, list[dict[str, Any]]]:
    """Deterministic 70/15/15 split keyed on (seed, scenario id).

    Mirrors the behaviour of ``split_scenarios.split_scenarios`` but
    works on dict scenarios (no Scenario dataclass needed) so the
    reference-routing schema can stay minimal.
    """
    if min(train_ratio, dev_ratio, test_ratio) < 0:
        raise ValueError("Ratios must be non-negative")
    total = train_ratio + dev_ratio + test_ratio
    if total <= 0:
        raise ValueError("Ratios must sum to a positive value")
    train_ratio /= total
    dev_ratio /= total

    digest_seed = str(seed).encode("utf-8")

    def _stable_key(entry: dict[str, Any]) -> tuple[str, str]:
        sid = entry["id"]
        h = hashlib.sha256(digest_seed + sid.encode("utf-8")).hexdigest()
        return (h, sid)

    ordered = sorted(scenarios, key=_stable_key)
    n = len(ordered)
    train_end = round(n * train_ratio)
    dev_end = train_end + round(n * dev_ratio)
    # Guarantee at least one example per bucket when n >= 3.
    if n >= 3:
        train_end = max(1, train_end)
        dev_end = max(train_end + 1, dev_end)
        if dev_end >= n:
            dev_end = n - 1
    return {
        "train": ordered[:train_end],
        "dev": ordered[train_end:dev_end],
        "test": ordered[dev_end:],
    }


def _load_scenarios(path: Path) -> list[dict[str, Any]]:
    """Load and validate reference-routing scenarios from YAML."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("scenarios") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise TypeError(
            f"Expected a top-level `scenarios:` list in {path}; got "
            f"{type(raw).__name__}."
        )
    scenarios: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise TypeError(f"scenarios[{idx}] in {path} is not a mapping")
        sid = entry.get("id")
        if not isinstance(sid, str) or not sid:
            raise ValueError(f"scenarios[{idx}] in {path} has no `id`")
        if sid in seen_ids:
            raise ValueError(f"duplicate scenario id {sid!r} in {path}")
        seen_ids.add(sid)
        gold = entry.get("gold_reference")
        if gold not in REFERENCE_NAMES:
            raise ValueError(
                f"{sid}: gold_reference={gold!r} is not in the canonical "
                f"inventory {REFERENCE_NAMES}"
            )
        band = entry.get("current_recall_band", "NONE")
        if band not in {"HIGH", "MEDIUM", "LOW", "NONE"}:
            raise ValueError(
                f"{sid}: current_recall_band={band!r} must be one of "
                "HIGH/MEDIUM/LOW/NONE."
            )
        prompt = entry.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError(f"{sid}: prompt must be a non-empty string")
        installed = entry.get("installed_capabilities") or []
        if not isinstance(installed, list):
            raise TypeError(f"{sid}: installed_capabilities must be a list")
        scenarios.append({
            "id": sid,
            "prompt": prompt,
            "user_prompt": prompt,
            "installed_capabilities": list(installed),
            "current_recall_band": band,
            "gold_reference": gold,
            "suite": gold,  # use the gold class as the suite key
            "why": entry.get("why", ""),
        })
    return scenarios


def _build_examples(
    bucket: list[dict[str, Any]],
) -> list[dspy.Example]:
    examples: list[dspy.Example] = []
    for entry in bucket:
        installed = ",".join(entry.get("installed_capabilities", []))
        ex = dspy.Example(
            id=entry["id"],
            suite=entry["suite"],
            user_prompt=entry["user_prompt"],
            installed_capabilities=installed,
            current_recall_band=entry["current_recall_band"],
            reference=entry["gold_reference"],
            reason="",
        ).with_inputs(
            "user_prompt",
            "installed_capabilities",
            "current_recall_band",
        )
        examples.append(ex)
    return examples


def _evaluate_module(
    module: Any,
    examples: list[dspy.Example],
    metric: ReferenceRoutingMetric,
) -> tuple[
    list[float],
    list[dict[str, Any]],
    list[float],
    list[ReferenceRoutingFinding],
]:
    """Score ``module`` and collect findings for aggregate-rate reporting."""
    final_scores: list[float] = []
    routing_scores: list[float] = []
    breakdown: list[dict[str, Any]] = []
    findings_all: list[ReferenceRoutingFinding] = []
    for ex in examples:
        try:
            pred = module(
                user_prompt=ex.user_prompt,
                installed_capabilities=getattr(
                    ex, "installed_capabilities", ""
                ),
                current_recall_band=getattr(ex, "current_recall_band", "NONE"),
            )
            routing_score, finding = metric.evaluate_with_finding(ex, pred)
            final_score = routing_score * metric._policy_token_factor
            error: str | None = None
        except Exception as exc:  # pragma: no cover — guard for LM failures
            routing_score = 0.0
            final_score = 0.0
            finding = ReferenceRoutingFinding(
                ReferenceRoutingFinding.INVALID,
                getattr(ex, "reference", ""),
                "",
                f"{type(exc).__name__}: {exc}",
            )
            error = f"{type(exc).__name__}: {exc}"

        final_scores.append(final_score)
        routing_scores.append(routing_score)
        findings_all.append(finding)
        breakdown.append({
            "id": getattr(ex, "id", "unknown"),
            "suite": getattr(ex, "suite", "unknown"),
            "gold": finding.gold,
            "pred": finding.pred,
            "kind": finding.kind,
            "routing_score": round(routing_score, 4),
            "final_score": round(final_score, 4),
            "score": round(final_score, 4),
            "policy_token_factor": round(metric._policy_token_factor, 4),
            "message": finding.message,
            "error": error,
        })
    return final_scores, breakdown, routing_scores, findings_all


def _per_suite_averages(breakdown: list[dict[str, Any]]) -> dict[str, float]:
    by_suite: dict[str, list[float]] = {}
    for entry in breakdown:
        suite = entry.get("suite", "unknown") or "unknown"
        by_suite.setdefault(suite, []).append(float(entry.get("score", 0.0)))
    return {
        suite: round(sum(scores) / len(scores), 4)
        for suite, scores in by_suite.items()
        if scores
    }


def _per_suite_failure_counts(
    breakdown: list[dict[str, Any]],
) -> dict[str, int]:
    by_suite: dict[str, int] = {}
    for entry in breakdown:
        suite = entry.get("suite", "unknown") or "unknown"
        if entry.get("kind") != ReferenceRoutingFinding.EXACT:
            by_suite[suite] = by_suite.get(suite, 0) + 1
    return by_suite


def _approx_tokens(text: str) -> int:
    return len(text) // 4


def _baseline_program_tokens() -> int:
    """Token estimate for the zero-shot reference-routing signature."""
    return _approx_tokens(ReferenceRoutingSignature.__doc__ or "")


def _optimized_program_tokens(optimized: Any) -> int:
    predictor = getattr(optimized, "predictor", None)
    instructions = ""
    demos: list[Any] = []
    if predictor is not None:
        sig = getattr(predictor, "signature", None)
        if sig is not None:
            instructions = getattr(sig, "instructions", "") or ""
        demos = list(getattr(predictor, "demos", []) or [])
    demos_blob = json.dumps([_demo_to_dict(d) for d in demos])
    return _approx_tokens(instructions) + _approx_tokens(demos_blob)


def _split_hash(split: dict[str, Any]) -> str:
    parts: list[str] = []
    for bucket in ("train", "dev", "test"):
        ids = sorted(e["id"] for e in split.get(bucket, []))
        parts.append(f"{bucket}:{','.join(ids)}")
    blob = "|".join(parts)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def run_optimization(
    *,
    scenarios_path: Path,
    optimizer_name: str,
    seed: int = 42,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run reference-routing optimisation; return the candidate report.

    Mirror of ``optimize_policy.run_optimization`` field-for-field on
    the report shape so ``render_candidate.py`` can consume it.
    """
    metric = ReferenceRoutingMetric()
    _configure_dspy_lm_from_env()

    raw_scenarios = _load_scenarios(scenarios_path)
    split = _split_scenarios(raw_scenarios, seed=seed)

    train_examples = _build_examples(split["train"])
    dev_examples = _build_examples(split["dev"])
    test_examples = _build_examples(split.get("test", []))

    if not train_examples:
        raise ValueError("No training examples after split")
    if not dev_examples:
        raise ValueError("No dev examples after split")

    baseline_module = ReferenceRoutingModule()
    (
        baseline_scores,
        baseline_breakdown,
        _baseline_routing_scores,
        baseline_findings,
    ) = _evaluate_module(baseline_module, dev_examples, metric)

    optimizer_factory = OPTIMIZERS.get(optimizer_name)
    if optimizer_factory is None:
        raise ValueError(
            f"Unknown optimizer '{optimizer_name}'. "
            f"Available: {sorted(OPTIMIZERS)}"
        )
    # The OPTIMIZERS factory is typed for DecisionPolicyMetric, but
    # the DSPy optimisers accept any callable metric — including this
    # one.  Cast through Any to satisfy mypy without widening the
    # decision-policy factory's published signature.
    optimizer = optimizer_factory(cast("Any", metric))

    module = ReferenceRoutingModule()
    if optimizer_name == "gepa":
        optimized = optimizer.compile(
            module,
            trainset=train_examples,
            valset=dev_examples,
        )
    else:
        optimized = optimizer.compile(module, trainset=train_examples)

    predictor = getattr(optimized, "predictor", None)
    program_instructions = (
        getattr(predictor.signature, "instructions", "") if predictor else ""
    )
    program_demos = tuple(
        _demo_to_dict(d) for d in (getattr(predictor, "demos", None) or ())
    )
    optimized_metric = ReferenceRoutingMetric(
        program_instructions=program_instructions,
        program_demos=program_demos,
    )

    dev_scores, dev_breakdown, dev_routing_scores, dev_findings = (
        _evaluate_module(optimized, dev_examples, optimized_metric)
    )

    if test_examples:
        (
            baseline_test_scores,
            baseline_test_breakdown,
            _,
            baseline_test_findings,
        ) = _evaluate_module(ReferenceRoutingModule(), test_examples, metric)
        (
            test_scores,
            test_breakdown,
            test_routing_scores,
            test_findings,
        ) = _evaluate_module(optimized, test_examples, optimized_metric)
    else:
        baseline_test_scores, baseline_test_breakdown = [], []
        baseline_test_findings = []
        test_scores, test_breakdown = [], []
        test_routing_scores = []
        test_findings = []

    def _avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    baseline_avg = _avg(baseline_scores)
    avg_dev = _avg(dev_scores)
    avg_dev_routing = _avg(dev_routing_scores)
    baseline_test_avg = _avg(baseline_test_scores)
    avg_test = _avg(test_scores)
    avg_test_routing = _avg(test_routing_scores)

    baseline_rates = aggregate_rates(baseline_findings)
    optimized_rates = aggregate_rates(dev_findings)
    baseline_test_rates = aggregate_rates(baseline_test_findings)
    optimized_test_rates = aggregate_rates(test_findings)

    baseline_program_tokens = _baseline_program_tokens()
    optimized_program_tokens = _optimized_program_tokens(optimized)

    program_path: Path | None = None
    if output_path is not None:
        program_path = output_path.with_suffix(".program.json")

    report: dict[str, Any] = {
        "signature": SIGNATURE_NAME,
        "timestamp": datetime.now(UTC).isoformat(),
        "optimizer": optimizer_name,
        "seed": seed,
        "train_count": len(train_examples),
        "dev_count": len(dev_examples),
        "test_count": len(test_examples),
        "baseline_dev_score_avg": round(baseline_avg, 4),
        "dev_score_avg": round(avg_dev, 4),
        "routing_score_avg": round(avg_dev_routing, 4),
        "final_score_avg": round(avg_dev, 4),
        "policy_token_factor": round(optimized_metric._policy_token_factor, 4),
        "delta": round(avg_dev - baseline_avg, 4),
        "baseline_test_score_avg": round(baseline_test_avg, 4),
        "test_score_avg": round(avg_test, 4),
        "test_routing_score_avg": round(avg_test_routing, 4),
        "test_final_score_avg": round(avg_test, 4),
        "test_delta": round(avg_test - baseline_test_avg, 4),
        "dev_scores": [round(s, 4) for s in dev_scores],
        "baseline_dev_scores": [round(s, 4) for s in baseline_scores],
        "test_scores": [round(s, 4) for s in test_scores],
        "baseline_test_scores": [round(s, 4) for s in baseline_test_scores],
        "dev_breakdown": dev_breakdown,
        "baseline_breakdown": baseline_breakdown,
        "test_breakdown": test_breakdown,
        "baseline_test_breakdown": baseline_test_breakdown,
        "dev_per_suite": _per_suite_averages(dev_breakdown),
        "baseline_dev_per_suite": _per_suite_averages(baseline_breakdown),
        "test_per_suite": _per_suite_averages(test_breakdown),
        "baseline_test_per_suite": _per_suite_averages(
            baseline_test_breakdown
        ),
        "dev_failures_per_suite": _per_suite_failure_counts(dev_breakdown),
        "test_failures_per_suite": _per_suite_failure_counts(test_breakdown),
        "baseline_program_tokens": baseline_program_tokens,
        "optimized_program_tokens": optimized_program_tokens,
        "token_delta": optimized_program_tokens - baseline_program_tokens,
        "model_matrix": _capture_model_matrix(optimizer_name),
        "scenarios_dir": str(scenarios_path),
        "split_hash": _split_hash(split),
        "optimizer_config": dict(OPTIMIZER_CONFIGS.get(optimizer_name, {})),
        "program_path": str(program_path) if program_path else None,
        # Reference-routing-specific aggregates.
        "false_positive_rate_on_none_avg": round(
            optimized_rates["false_positive_rate_on_none"], 4
        ),
        "false_negative_rate_on_named_avg": round(
            optimized_rates["false_negative_rate_on_named"], 4
        ),
        "baseline_false_positive_rate_on_none_avg": round(
            baseline_rates["false_positive_rate_on_none"], 4
        ),
        "baseline_false_negative_rate_on_named_avg": round(
            baseline_rates["false_negative_rate_on_named"], 4
        ),
        "test_false_positive_rate_on_none_avg": round(
            optimized_test_rates["false_positive_rate_on_none"], 4
        ),
        "test_false_negative_rate_on_named_avg": round(
            optimized_test_rates["false_negative_rate_on_named"], 4
        ),
        "baseline_test_false_positive_rate_on_none_avg": round(
            baseline_test_rates["false_positive_rate_on_none"], 4
        ),
        "per_class_accuracy": optimized_rates["per_class_accuracy"],
        "baseline_per_class_accuracy": baseline_rates["per_class_accuracy"],
        "invalid_predictions": optimized_rates["invalid_predictions"],
        "invalid_classes": optimized_rates["invalid_classes"],
        "canonical_reference_names": list(REFERENCE_NAMES),
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    if program_path is not None:
        program_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            optimized.save(str(program_path))
        except OSError as exc:
            print(
                f"warning: failed to save compiled program to "
                f"{program_path}: {exc}",
                file=sys.stderr,
            )
            report["program_path"] = None

    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run DSPy offline optimisation for the reference-routing "
            "signature."
        )
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path("evals/scenarios/reference_routing/scenarios.yaml"),
        help="Path to the reference-routing scenarios YAML.",
    )
    parser.add_argument(
        "--optimizer",
        default="bootstrap_few_shot",
        choices=sorted(OPTIMIZERS),
        help="DSPy optimizer to use.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for scenario splitting.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to write the candidate report JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = run_optimization(
            scenarios_path=args.scenarios,
            optimizer_name=args.optimizer,
            seed=args.seed,
            output_path=args.output,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"signature={report['signature']} "
        f"optimizer={report['optimizer']} "
        f"baseline={report['baseline_dev_score_avg']} "
        f"dev={report['dev_score_avg']} "
        f"dev_delta={report['delta']:+.4f} "
        f"test={report['test_score_avg']} "
        f"test_delta={report['test_delta']:+.4f} "
        f"fp_none={report['false_positive_rate_on_none_avg']} "
        f"fn_named={report['false_negative_rate_on_named_avg']} "
        f"tokens={report['baseline_program_tokens']}->"
        f"{report['optimized_program_tokens']} "
        f"(Δ{report['token_delta']:+d})"
    )
    if args.output:
        print(f"report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

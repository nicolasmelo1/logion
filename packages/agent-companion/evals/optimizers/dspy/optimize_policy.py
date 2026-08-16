# SPDX-License-Identifier: MIT
"""Offline DSPy optimizer for the bootstrap decision policy.

Runs DSPy optimization (e.g. MIPROv2 or BootstrapFewShot) against the
eval scenarios to produce candidate policy prompt improvements. Generated
candidates are written to ``generated_candidates/`` and are **never**
auto-promoted — a human must review the diff before any changes to
``SKILL.md``.

DSPy is an optional extra. Install with::

    pip install -e '.[dspy]'

Usage::

    python evals/optimizers/dspy/optimize_policy.py \\
        --scenarios evals/scenarios \\
        --catalog evals/catalogs/fake-marketplace.yaml \\
        --optimizer bootstrap_few_shot \\
        --output evals/optimizers/dspy/generated_candidates/candidate-001.json

Requires a running LLM endpoint (set ``DSPY_LM`` env var, e.g.
``DSPY_LM=openai/qwen3-8b-q5km`` with appropriate base URL).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

# Allow `python evals/optimizers/dspy/optimize_policy.py` from the
# package root.  evals/ is not part of the installed wheel.
ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dspy

from evals.harness._json import JsonObject
from evals.harness.schema import Catalog, load_catalog, load_scenarios_from_dir
from evals.optimizers.dspy.metrics import (
    DecisionPolicyMetric,
)
from evals.optimizers.dspy.signatures import DecisionPolicyModule
from evals.optimizers.dspy.split_scenarios import split_scenarios

_BOOTSTRAP_FEW_SHOT_CONFIG: JsonObject = {
    "max_bootstrapped_demos": 4,
    "max_labeled_demos": 8,
}

_MIPRO_V2_CONFIG: JsonObject = {
    "auto": "medium",
    "num_threads": 1,
}

# GEPA's ``auto`` budget knob (light / medium / heavy).  Override via
# the ``LOGION_GEPA_AUTO`` env var without editing the file.  Default
# stays at ``light`` because heavier budgets multiply rollout count
# and we've seen reflection-bloat get worse, not better, with more
# iterations on this signature.
_GEPA_CONFIG: JsonObject = {
    "auto": os.environ.get("LOGION_GEPA_AUTO", "light"),
}


class Metric(Protocol):
    """The DSPy metric surface the optimizer factories require.

    Widening the factories to this Protocol is what lets the reference
    routing optimizer reuse them: it has its own metric class, and the
    two share no base.
    """

    def __call__(
        self,
        gold: object,
        pred: object,
        trace: object = ...,
        pred_name: object = ...,
        pred_trace: object = ...,
        **kwargs: object,
    ) -> float | JsonObject: ...


class CompiledProgram(Protocol):
    """The compiled DSPy program surface this optimizer relies on."""

    def save(self, path: str) -> None: ...


class Teleprompter(Protocol):
    """The DSPy optimizer surface this module relies on.

    A Protocol rather than a union of the three concrete DSPy classes:
    BootstrapFewShot, MIPROv2 and GEPA share no useful base, and only
    ``compile`` is ever called on them here.
    """

    def compile(
        self, student: object, /, **kwargs: object
    ) -> CompiledProgram: ...


def _bootstrap_few_shot(metric: Metric) -> Teleprompter:
    return dspy.BootstrapFewShot(metric=metric, **_BOOTSTRAP_FEW_SHOT_CONFIG)


def _mipro_v2(metric: Metric) -> Teleprompter:
    return dspy.MIPROv2(metric=metric, **_MIPRO_V2_CONFIG)


def _build_reflection_lm() -> object:
    """Build the GEPA reflection LM from env, defaulting to the task LM."""
    model = os.environ.get("DSPY_REFLECTION_LM") or os.environ.get("DSPY_LM")
    if not model:
        raise ValueError(
            "GEPA requires a reflection LM: set DSPY_REFLECTION_LM (or "
            "fall back to DSPY_LM)."
        )
    kwargs: JsonObject = {}
    api_base = os.environ.get("DSPY_REFLECTION_API_BASE") or os.environ.get(
        "DSPY_API_BASE"
    )
    api_key = os.environ.get("DSPY_REFLECTION_API_KEY") or os.environ.get(
        "DSPY_API_KEY"
    )
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    # GEPA's reflection step benefits from higher max_tokens and
    # non-zero temperature per upstream guidance.
    kwargs.setdefault("temperature", 1.0)
    kwargs.setdefault("max_tokens", 8000)
    return dspy.LM(model, **kwargs)


def _gepa(metric: Metric) -> Teleprompter:
    return dspy.GEPA(
        metric=metric,
        reflection_lm=_build_reflection_lm(),
        **_GEPA_CONFIG,
    )


OPTIMIZERS = {
    "bootstrap_few_shot": _bootstrap_few_shot,
    "mipro_v2": _mipro_v2,
    "gepa": _gepa,
}

OPTIMIZER_CONFIGS: dict[str, JsonObject] = {
    "bootstrap_few_shot": _BOOTSTRAP_FEW_SHOT_CONFIG,
    "mipro_v2": _MIPRO_V2_CONFIG,
    "gepa": _GEPA_CONFIG,
}


def _catalog_summary(catalog: Catalog) -> str:
    """Return compact marketplace context for optimizer examples."""
    lines: list[str] = []
    for course in catalog.courses:
        price = "free" if course.is_free else f"${course.price_usd:.2f}"
        tags = ",".join(course.tags)
        capabilities = ",".join(course.capability_ids)
        lines.append(
            f"{course.id}: {course.name} ({price}; status="
            f"{course.review_status}; tags={tags}; "
            f"capabilities={capabilities}) — {course.summary}"
        )
    return "\n".join(lines)


def _current_policy_text() -> str:
    """Read the current bootstrap policy text used as optimizer input."""
    return (ROOT / "SKILL.md").read_text(encoding="utf-8")


def _configure_dspy_lm_from_env() -> None:
    """Configure DSPy's default LM from the documented environment vars."""
    model = os.environ.get("DSPY_LM")
    if not model:
        raise ValueError(
            "DSPY_LM must be set before running optimization, e.g. "
            "DSPY_LM=openai/model-name"
        )

    kwargs: dict[str, str] = {}
    api_base = os.environ.get("DSPY_API_BASE")
    api_key = os.environ.get("DSPY_API_KEY")
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    dspy.configure(lm=dspy.LM(model, **kwargs))


def _build_examples(
    bucket_scenarios: list[JsonObject],
    *,
    catalog: Catalog,
    current_policy_text: str,
) -> list[dspy.Example]:
    """Convert split JSON entries to DSPy Examples."""
    marketplace_results = _catalog_summary(catalog)
    examples: list[dspy.Example] = []
    for entry in bucket_scenarios:
        installed_capabilities = ",".join(
            entry.get("installed_capabilities", [])
        )
        payload = dict(entry)
        payload.update({
            "installed_capabilities": installed_capabilities,
            "marketplace_results": entry.get(
                "marketplace_results", marketplace_results
            ),
            "current_policy_text": entry.get(
                "current_policy_text", current_policy_text
            ),
        })
        ex = dspy.Example(**payload).with_inputs(
            "user_prompt",
            "installed_capabilities",
            "marketplace_results",
            "current_policy_text",
        )
        examples.append(ex)
    return examples


def _load_split(path: Path) -> dict[str, list[JsonObject]]:
    """Load a previously written split JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["splits"]


def _evaluate_module(
    module: object,
    dev_examples: list[dspy.Example],
    metric: DecisionPolicyMetric,
) -> tuple[list[float], list[JsonObject], list[float]]:
    """Score ``module`` on dev examples; return per-scenario findings.

    Returns ``(final_scores, breakdown, routing_scores)`` where
    ``routing_scores`` are the pre-token-factor scores and
    ``final_scores`` are the routing scores multiplied by the metric's
    ``_policy_token_factor``.
    """
    final_scores: list[float] = []
    routing_scores: list[float] = []
    breakdown: list[JsonObject] = []
    for ex in dev_examples:
        try:
            pred = module(
                user_prompt=ex.user_prompt,
                installed_capabilities=getattr(
                    ex, "installed_capabilities", ""
                ),
                marketplace_results=getattr(ex, "marketplace_results", ""),
                current_policy_text=getattr(ex, "current_policy_text", ""),
            )
            routing_score, findings = metric.evaluate_with_findings(ex, pred)
            final_score = routing_score * metric._policy_token_factor
            failures = [
                {"metric": f.metric, "detail": f.message}
                for f in findings
                if not f.passed
            ]
            error: str | None = None
        except Exception as exc:
            routing_score = 0.0
            final_score = 0.0
            failures = []
            error = f"{type(exc).__name__}: {exc}"

        final_scores.append(final_score)
        routing_scores.append(routing_score)
        breakdown.append({
            "id": getattr(ex, "id", "unknown"),
            "suite": getattr(ex, "suite", "unknown"),
            "routing_score": round(routing_score, 4),
            "final_score": round(final_score, 4),
            "score": round(final_score, 4),
            "policy_token_factor": round(metric._policy_token_factor, 4),
            "failures": failures,
            "error": error,
        })
    return final_scores, breakdown, routing_scores


def _per_suite_averages(breakdown: list[JsonObject]) -> dict[str, float]:
    """Aggregate per-scenario scores into per-suite averages."""
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
    breakdown: list[JsonObject],
) -> dict[str, int]:
    """Count scenarios with at least one failure per suite."""
    by_suite: dict[str, int] = {}
    for entry in breakdown:
        suite = entry.get("suite", "unknown") or "unknown"
        failures = entry.get("failures") or []
        if failures or entry.get("error"):
            by_suite[suite] = by_suite.get(suite, 0) + 1
    return by_suite


def _approx_tokens(text: str) -> int:
    """4-chars-per-token estimate. Good enough for English policy text."""
    return len(text) // 4


def _baseline_program_tokens() -> int:
    """Token estimate for the zero-shot policy: signature docstring only."""
    docstring = DecisionPolicyModule().predictor.signature.__doc__ or ""
    return _approx_tokens(docstring)


def _demo_to_dict(demo: object) -> JsonObject:
    """Best-effort conversion of a DSPy demo to a JSON-able dict."""
    to_dict = getattr(demo, "toDict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(demo, dict):
        return dict(demo)
    return {}


def _optimized_program_tokens(optimized: object) -> int:
    """Token estimate for compiled program: instructions + serialized demos."""
    predictor = getattr(optimized, "predictor", None)
    instructions = ""
    demos: list[object] = []
    if predictor is not None:
        sig = getattr(predictor, "signature", None)
        if sig is not None:
            instructions = getattr(sig, "instructions", "") or ""
        demos = list(getattr(predictor, "demos", []) or [])
    demos_blob = json.dumps([_demo_to_dict(d) for d in demos])
    return _approx_tokens(instructions) + _approx_tokens(demos_blob)


def _capture_model_matrix(optimizer_name: str) -> JsonObject:
    """Record the LM and optimizer configuration used for this run."""
    matrix: JsonObject = {
        "dspy_lm": os.environ.get("DSPY_LM", ""),
        "dspy_api_base": os.environ.get("DSPY_API_BASE", ""),
        "optimizer": optimizer_name,
        "optimizer_config": dict(OPTIMIZER_CONFIGS.get(optimizer_name, {})),
    }
    if optimizer_name == "gepa":
        matrix["dspy_reflection_lm"] = os.environ.get(
            "DSPY_REFLECTION_LM", ""
        ) or os.environ.get("DSPY_LM", "")
        matrix["dspy_reflection_api_base"] = os.environ.get(
            "DSPY_REFLECTION_API_BASE", ""
        ) or os.environ.get("DSPY_API_BASE", "")
    return matrix


def run_optimization(
    *,
    scenarios_path: Path,
    catalog_path: Path,
    optimizer_name: str,
    seed: int = 42,
    split_path: Path | None = None,
    output_path: Path | None = None,
) -> JsonObject:
    """Run a DSPy optimizer and return the candidate report.

    If ``split_path`` is provided, the train/dev/test split is loaded
    from the JSON file written by ``split_scenarios.py``. Otherwise the
    scenarios are split in-process using ``seed``.

    The report includes both the baseline (un-optimized) and optimized
    dev scores so reviewers can see whether the optimizer actually
    helped before promoting any changes to SKILL.md. The compiled
    program is saved alongside the report so reviewers can inspect the
    rewritten signature instructions and selected demos.
    """
    catalog = load_catalog(catalog_path)
    metric = DecisionPolicyMetric(catalog)
    _configure_dspy_lm_from_env()

    if split_path is not None:
        split = _load_split(split_path)
    else:
        scenarios = load_scenarios_from_dir(scenarios_path)
        split = split_scenarios(scenarios, seed=seed)

    current_policy = _current_policy_text()
    train_examples = _build_examples(
        split["train"], catalog=catalog, current_policy_text=current_policy
    )
    dev_examples = _build_examples(
        split["dev"], catalog=catalog, current_policy_text=current_policy
    )

    if not train_examples:
        raise ValueError("No training examples after split")
    if not dev_examples:
        raise ValueError("No dev examples after split")

    # Baseline: score the un-optimized module on the same dev set so
    # the report carries a delta. Without this you cannot tell whether
    # the optimizer produced anything useful or just noise.
    baseline_module = DecisionPolicyModule()
    (
        baseline_scores,
        baseline_breakdown,
        _baseline_routing_scores,
    ) = _evaluate_module(baseline_module, dev_examples, metric)

    optimizer_factory = OPTIMIZERS.get(optimizer_name)
    if optimizer_factory is None:
        raise ValueError(
            f"Unknown optimizer '{optimizer_name}'. "
            f"Available: {sorted(OPTIMIZERS)}"
        )
    optimizer = optimizer_factory(metric)

    module = DecisionPolicyModule()
    if optimizer_name == "gepa":
        # GEPA uses an explicit validation set; pass the dev split as
        # the valset so it can reflect against held-out signal during
        # evolution.
        optimized = optimizer.compile(
            module,
            trainset=train_examples,
            valset=dev_examples,
        )
    else:
        optimized = optimizer.compile(
            module,
            trainset=train_examples,
        )

    # Build a token-aware metric for the optimized program. Baseline
    # evaluations keep the un-instrumented metric (factor 1.0).
    predictor = getattr(optimized, "predictor", None)
    program_instructions = (
        getattr(predictor.signature, "instructions", "") if predictor else ""
    )
    program_demos = tuple(
        _demo_to_dict(d) for d in (getattr(predictor, "demos", None) or ())
    )
    optimized_metric = DecisionPolicyMetric(
        catalog,
        program_instructions=program_instructions,
        program_demos=program_demos,
    )

    dev_scores, dev_breakdown, dev_routing_scores = _evaluate_module(
        optimized, dev_examples, optimized_metric
    )

    # Holdout test pass: never seen by the optimizer; this is the
    # number that gates promotion.
    test_examples = _build_examples(
        split.get("test", []),
        catalog=catalog,
        current_policy_text=current_policy,
    )
    if test_examples:
        baseline_test_scores, baseline_test_breakdown, _ = _evaluate_module(
            DecisionPolicyModule(), test_examples, metric
        )
        test_scores, test_breakdown, test_routing_scores = _evaluate_module(
            optimized, test_examples, optimized_metric
        )
    else:
        baseline_test_scores, baseline_test_breakdown = [], []
        test_scores, test_breakdown = [], []
        test_routing_scores = []

    baseline_avg = (
        sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0.0
    )
    avg_dev = sum(dev_scores) / len(dev_scores) if dev_scores else 0.0
    avg_dev_routing = (
        sum(dev_routing_scores) / len(dev_routing_scores)
        if dev_routing_scores
        else 0.0
    )
    baseline_test_avg = (
        sum(baseline_test_scores) / len(baseline_test_scores)
        if baseline_test_scores
        else 0.0
    )
    avg_test = sum(test_scores) / len(test_scores) if test_scores else 0.0
    avg_test_routing = (
        sum(test_routing_scores) / len(test_routing_scores)
        if test_routing_scores
        else 0.0
    )

    baseline_program_tokens = _baseline_program_tokens()
    optimized_program_tokens = _optimized_program_tokens(optimized)

    # Compute the program-path string up-front so the report can carry
    # it even if the actual program-save fails (e.g. EMFILE on macOS
    # after a long GEPA run leaks file descriptors).  We attempt the
    # program save *after* the report write below so a save failure
    # doesn't lose the eval data — see the token-factor follow-up note.
    program_path: Path | None = None
    if output_path is not None:
        program_path = output_path.with_suffix(".program.json")

    report: JsonObject = {
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
        "catalog": str(catalog_path),
        "scenarios_dir": str(scenarios_path),
        "split_hash": _split_hash(split),
        "optimizer_config": dict(OPTIMIZER_CONFIGS.get(optimizer_name, {})),
        "program_path": str(program_path) if program_path else None,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    # Program save is best-effort.  A failure here (e.g. EMFILE after a
    # long-running DSPy session has leaked file descriptors) must not
    # invalidate the already-written eval report.  The renderer falls
    # back to the report alone when no program file exists.
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


def _split_hash(split: JsonObject) -> str:
    """Deterministic hash of the split assignment for reproducibility."""
    import hashlib

    parts: list[str] = []
    for bucket in ("train", "dev", "test"):
        ids = sorted(e["id"] for e in split.get(bucket, []))
        parts.append(f"{bucket}:{','.join(ids)}")
    blob = "|".join(parts)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run DSPy offline optimization for the decision policy."
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path("evals/scenarios"),
        help="Directory containing scenario YAML files.",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("evals/catalogs/fake-marketplace.yaml"),
        help="Path to the catalog YAML.",
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
        help="Seed for scenario splitting (ignored if --split is given).",
    )
    parser.add_argument(
        "--split",
        type=Path,
        dest="split_path",
        help="Path to a split JSON from split_scenarios.py. "
        "If provided, --scenarios and --seed are only used as "
        "fallback for in-process splitting.",
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
            catalog_path=args.catalog,
            optimizer_name=args.optimizer,
            seed=args.seed,
            split_path=args.split_path,
            output_path=args.output,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"optimizer={report['optimizer']} "
        f"baseline={report['baseline_dev_score_avg']} "
        f"dev={report['dev_score_avg']} "
        f"dev_delta={report['delta']:+.4f} "
        f"test={report['test_score_avg']} "
        f"test_delta={report['test_delta']:+.4f} "
        f"tokens={report['baseline_program_tokens']}->"
        f"{report['optimized_program_tokens']} "
        f"(Δ{report['token_delta']:+d})"
    )
    if args.output:
        print(f"report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

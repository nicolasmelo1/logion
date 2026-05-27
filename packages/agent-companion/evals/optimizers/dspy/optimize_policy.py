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
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Allow `python evals/optimizers/dspy/optimize_policy.py` from the
# package root.  evals/ is not part of the installed wheel.
ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dspy

from evals.harness.schema import load_catalog, load_scenarios_from_dir
from evals.optimizers.dspy.metrics import DecisionPolicyMetric
from evals.optimizers.dspy.signatures import DecisionPolicyModule
from evals.optimizers.dspy.split_scenarios import split_scenarios

OPTIMIZERS = {
    "bootstrap_few_shot": lambda: dspy.BootstrapFewShot(
        max_bootstrapped_demos=4,
        max_labeled_demos=8,
    ),
    "mipro_v2": lambda: dspy.MIPROv2(
        auto="medium",
        num_threads=1,
    ),
}


def _build_examples(
    bucket_scenarios: list[dict[str, Any]],
) -> list[dspy.Example]:
    """Convert split JSON entries to DSPy Examples."""
    examples: list[dspy.Example] = []
    for entry in bucket_scenarios:
        ex = dspy.Example(
            user_prompt=entry["user_prompt"],
            installed_capabilities=",".join(
                entry.get("installed_capabilities", [])
            ),
            marketplace_results=entry.get("marketplace_results", ""),
            current_policy_text=entry.get("current_policy_text", ""),
        ).with_inputs(
            "user_prompt",
            "installed_capabilities",
            "marketplace_results",
            "current_policy_text",
        )
        for key, val in entry.items():
            if not hasattr(ex, key):
                setattr(ex, key, val)
        examples.append(ex)
    return examples


def _load_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load a previously written split JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["splits"]


def run_optimization(
    *,
    scenarios_path: Path,
    catalog_path: Path,
    optimizer_name: str,
    seed: int = 42,
    split_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run a DSPy optimizer and return the candidate report.

    If ``split_path`` is provided, the train/dev/test split is loaded
    from the JSON file written by ``split_scenarios.py``. Otherwise the
    scenarios are split in-process using ``seed``.
    """
    catalog = load_catalog(catalog_path)
    metric = DecisionPolicyMetric(catalog)

    if split_path is not None:
        split = _load_split(split_path)
    else:
        scenarios = load_scenarios_from_dir(scenarios_path)
        split = split_scenarios(scenarios, seed=seed)

    train_examples = _build_examples(split["train"])
    dev_examples = _build_examples(split["dev"])

    if not train_examples:
        raise ValueError("No training examples after split")
    if not dev_examples:
        raise ValueError("No dev examples after split")

    optimizer_factory = OPTIMIZERS.get(optimizer_name)
    if optimizer_factory is None:
        raise ValueError(
            f"Unknown optimizer '{optimizer_name}'. "
            f"Available: {sorted(OPTIMIZERS)}"
        )
    optimizer = optimizer_factory()

    module = DecisionPolicyModule()
    optimized = optimizer.compile(
        module,
        trainset=train_examples,
        eval_kwargs={"metric": metric},
    )

    # Evaluate dev set with the optimized module
    dev_scores: list[float] = []
    for ex in dev_examples:
        pred = optimized(
            user_prompt=ex.user_prompt,
            installed_capabilities=getattr(ex, "installed_capabilities", ""),
            marketplace_results=getattr(ex, "marketplace_results", ""),
            current_policy_text=getattr(ex, "current_policy_text", ""),
        )
        score = metric(ex, pred)
        dev_scores.append(score)

    avg_dev = sum(dev_scores) / len(dev_scores) if dev_scores else 0.0

    report: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "optimizer": optimizer_name,
        "seed": seed,
        "train_count": len(train_examples),
        "dev_count": len(dev_examples),
        "test_count": len(split["test"]),
        "dev_score_avg": round(avg_dev, 4),
        "dev_scores": [round(s, 4) for s in dev_scores],
        "catalog": str(catalog_path),
        "scenarios_dir": str(scenarios_path),
        "split_hash": _split_hash(split),
        "optimizer_config": str(optimizer),
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    return report


def _split_hash(split: dict[str, Any]) -> str:
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
        f"dev_avg={report['dev_score_avg']} "
        f"train={report['train_count']} "
        f"dev={report['dev_count']} "
        f"test={report['test_count']}"
    )
    if args.output:
        print(f"report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

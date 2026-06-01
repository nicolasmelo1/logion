# SPDX-License-Identifier: MIT
"""Split eval scenarios into train, dev, and test sets.

Produces deterministic splits so DSPy optimization experiments are
reproducible. The split is based on a hash of the scenario ID and a
configurable seed, not on file order.

Usage::

    python evals/optimizers/dspy/split_scenarios.py \\
        --scenarios evals/scenarios \\
        --seed 42 \\
        --ratios 0.6,0.2,0.2 \\
        --output evals/optimizers/dspy/generated_candidates/split.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Allow `python evals/optimizers/dspy/split_scenarios.py` from the
# package root.  evals/ is not part of the installed wheel.
ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.harness.schema import (
    Scenario,
    load_scenarios_from_dir,
)


def _stable_hash(text: str, seed: int) -> float:
    """Return a stable float in [0, 1) from text + seed."""
    h = hashlib.sha256(f"{seed}:{text}".encode()).hexdigest()
    return int(h[:8], 16) / 0x100000000


def _bucket_counts(
    total: int,
    *,
    train_ratio: float,
    dev_ratio: float,
    test_ratio: float,
) -> dict[str, int]:
    """Return exact split counts using largest-remainder rounding."""
    ratios = {
        "train": train_ratio,
        "dev": dev_ratio,
        "test": test_ratio,
    }
    raw_counts = {name: total * ratio for name, ratio in ratios.items()}
    counts = {name: int(value) for name, value in raw_counts.items()}
    remaining = total - sum(counts.values())

    by_remainder = sorted(
        raw_counts,
        key=lambda name: (raw_counts[name] - counts[name], ratios[name]),
        reverse=True,
    )
    for name in by_remainder[:remaining]:
        counts[name] += 1
    return counts


def _expected_dict(scenario: Scenario) -> dict[str, Any]:
    """Extract expected fields into a JSON-serializable dict."""
    return {
        "should_query_marketplace": (
            scenario.expected.should_query_marketplace
        ),
        "should_install": scenario.expected.should_install,
        "should_ask_confirmation": (scenario.expected.should_ask_confirmation),
        "should_run_recall": (scenario.expected.should_run_recall),
        "acceptable_course_ids": list(scenario.expected.acceptable_course_ids),
        "forbidden_course_ids": list(scenario.expected.forbidden_course_ids),
        "max_courses_inspected": (scenario.expected.max_courses_inspected),
        "max_loaded_skills": (scenario.expected.max_loaded_skills),
        "must_mention": list(scenario.expected.must_mention),
        "must_not_mention": list(scenario.expected.must_not_mention),
        "forbidden_tools": list(scenario.expected.forbidden_tools),
        "recall_bypass_allowed": (scenario.expected.recall_bypass_allowed),
    }


def split_scenarios(
    scenarios: list[Scenario],
    *,
    seed: int = 42,
    train_ratio: float = 0.6,
    dev_ratio: float = 0.2,
    test_ratio: float = 0.2,
) -> dict[str, list[dict[str, Any]]]:
    """Split scenarios into train, dev, and test by stable hash.

    Each scenario gets a deterministic bucket based on its ID hash.
    The ratios must sum to 1.0.
    """
    total = train_ratio + dev_ratio + test_ratio
    if min(train_ratio, dev_ratio, test_ratio) < 0:
        raise ValueError(
            "Ratios must be non-negative, got "
            f"train={train_ratio}, dev={dev_ratio}, test={test_ratio}"
        )
    if abs(total - 1.0) > 1e-9:
        raise ValueError(
            f"Ratios must sum to 1.0, got {total} "
            f"(train={train_ratio}, dev={dev_ratio}, "
            f"test={test_ratio})"
        )

    buckets: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "dev": [],
        "test": [],
    }

    counts = _bucket_counts(
        len(scenarios),
        train_ratio=train_ratio,
        dev_ratio=dev_ratio,
        test_ratio=test_ratio,
    )
    ordered = sorted(
        scenarios,
        key=lambda scenario: (_stable_hash(scenario.id, seed), scenario.id),
    )
    train_count = counts["train"]
    dev_end = train_count + counts["dev"]
    assignments = (
        ("train", ordered[:train_count]),
        ("dev", ordered[train_count:dev_end]),
        ("test", ordered[dev_end:]),
    )

    for bucket, bucket_scenarios in assignments:
        for scenario in bucket_scenarios:
            entry: dict[str, Any] = {
                "id": scenario.id,
                "suite": scenario.suite,
                "prompt": scenario.prompt,
                "user_prompt": scenario.prompt,
                "installed_capabilities": list(
                    scenario.installed_capabilities
                ),
                "local_recall": [dict(item) for item in scenario.local_recall],
                "catalog_fixture": scenario.catalog_fixture,
                "expected": _expected_dict(scenario),
            }
            if scenario.fake_trace.calls:
                entry["fake_trace"] = {
                    "calls": [
                        {"tool": c.tool, "args": dict(c.args)}
                        for c in scenario.fake_trace.calls
                    ],
                    "final_answer": (scenario.fake_trace.final_answer),
                    "selected_course_ids": list(
                        scenario.fake_trace.selected_course_ids
                    ),
                }
            buckets[bucket].append(entry)

    return buckets


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split eval scenarios for DSPy optimization."
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path("evals/scenarios"),
        help="Directory containing scenario YAML files.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Hash seed for deterministic splitting.",
    )
    parser.add_argument(
        "--ratios",
        type=str,
        default="0.6,0.2,0.2",
        help="Comma-separated train,dev,test ratios (must sum to 1).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evals/optimizers/dspy/generated_candidates/split.json"),
        help="Path to write the split JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    ratios = [float(r) for r in args.ratios.split(",")]
    if len(ratios) != 3:
        raise SystemExit("--ratios must be three comma-separated floats")

    scenarios = load_scenarios_from_dir(args.scenarios)
    buckets = split_scenarios(
        scenarios,
        seed=args.seed,
        train_ratio=ratios[0],
        dev_ratio=ratios[1],
        test_ratio=ratios[2],
    )

    output: dict[str, Any] = {
        "seed": args.seed,
        "ratios": {
            "train": ratios[0],
            "dev": ratios[1],
            "test": ratios[2],
        },
        "counts": {
            "train": len(buckets["train"]),
            "dev": len(buckets["dev"]),
            "test": len(buckets["test"]),
        },
        "splits": buckets,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    counts = output["counts"]
    total = sum(counts.values())
    print(
        f"Split {total} scenarios: "
        f"train={counts['train']} "
        f"dev={counts['dev']} "
        f"test={counts['test']} "
        f"-> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI for the eval harness.

Examples:
    python evals/run_eval.py \
        --provider fake \
        --scenarios evals/scenarios \
        --catalog evals/catalogs/fake-marketplace.yaml

    python evals/run_eval.py \
        --provider llama_cpp_local \
        --config evals/providers/llama_cpp_local.example.yaml \
        --model qwen3-8b-q5km \
        --scenarios evals/scenarios \
        --catalog evals/catalogs/fake-marketplace.yaml
"""

from __future__ import annotations

import argparse
import subprocess  # nosec B404 - local git metadata lookup only
import sys
from pathlib import Path
from typing import Any

# Allow `python evals/run_eval.py` from the package root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.harness.providers import (  # noqa: E402
    FakeProvider,
    LlamaCppProviderError,
    load_llama_cpp_provider,
)
from evals.harness.runner import (  # noqa: E402
    Provider,
    run,
    summarize,
    write_report,
)

# Scenarios designed to fail a specific grading tier.
# They give the grader a deterministic adversarial example but must
# not surface as failures in the green-path eval run — they have
# dedicated pytest assertions in test_eval_harness.py instead.
_ADVERSARIAL_SCENARIO_IDS = frozenset({
    "safety-bare-confirm-keyword-fails-tier2",
})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run companion evals.")
    parser.add_argument(
        "--provider",
        default="fake",
        choices=["fake", "llama_cpp_local"],
        help="Provider to use.",
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
        "--report",
        type=Path,
        default=Path("evals/reports/last-run.json"),
        help="Where to write the JSON report.",
    )
    parser.add_argument(
        "--model",
        default="fake-deterministic",
        help="Model identifier recorded in the trace.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Provider/model config YAML for live local evals.",
    )
    return parser.parse_args()


def _git_commit() -> str | None:
    try:
        result = subprocess.run(  # nosec - fixed local git query
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def _resolve_provider(
    args: argparse.Namespace,
) -> tuple[Provider, dict[str, Any]]:
    if args.provider == "fake":
        return (
            FakeProvider(model=args.model),
            {
                "provider": "fake",
                "model_id": args.model,
                "config_path": str(args.config) if args.config else None,
            },
        )
    if args.config is None:
        raise SystemExit(
            "--config is required when --provider=llama_cpp_local"
        )
    provider = load_llama_cpp_provider(args.config, args.model)
    return provider, provider.report_metadata()


def main() -> int:
    args = _parse_args()
    try:
        provider, run_metadata = _resolve_provider(args)
        results = run(args.scenarios, args.catalog, provider=provider)
    except LlamaCppProviderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    results = [
        r for r in results if r.scenario_id not in _ADVERSARIAL_SCENARIO_IDS
    ]
    summary = summarize(results)
    summary["run"] = {
        **run_metadata,
        "git_commit": _git_commit(),
        "report_path": str(args.report),
    }
    write_report(summary, args.report)
    totals = summary["totals"]
    print(
        f"scenarios={totals['scenarios']} "
        f"passed={totals['passed']} "
        f"failed={totals['failed']} "
        f"provider={summary['run']['provider']} "
        f"model={summary['run']['model_id']} "
        f"report={args.report}"
    )
    for failure in summary["failures"]:
        print(
            f"FAIL {failure['suite']}/{failure['scenario_id']}: "
            + "; ".join(
                f"{f['metric']}: {f['message']}" for f in failure["failures"]
            )
        )
    return 0 if totals["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

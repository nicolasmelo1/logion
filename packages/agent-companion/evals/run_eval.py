"""CLI for the eval harness.

Example:
    python evals/run_eval.py \\
        --provider fake \\
        --scenarios evals/scenarios \\
        --catalog evals/catalogs/fake-marketplace.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python evals/run_eval.py` from the package root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.harness.providers.fake import FakeProvider  # noqa: E402
from evals.harness.runner import run, summarize, write_report  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run companion evals.")
    parser.add_argument(
        "--provider",
        default="fake",
        choices=["fake"],
        help="Provider to use (currently only the deterministic fake).",
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
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    provider = FakeProvider(model=args.model)
    results = run(args.scenarios, args.catalog, provider=provider)
    summary = summarize(results)
    write_report(summary, args.report)
    totals = summary["totals"]
    print(
        f"scenarios={totals['scenarios']} "
        f"passed={totals['passed']} "
        f"failed={totals['failed']} "
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

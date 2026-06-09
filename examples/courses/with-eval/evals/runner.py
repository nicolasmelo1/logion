"""Deterministic eval runner for the with-eval course example.

For each scenario in scenarios.json:
  1. Read the agent's review from reviews/<scenario>.txt.
  2. Load the expected outcome from expected/<scenario>.json.
  3. Score by substring presence:
       - verdict 'must_flag': every required_categories item must appear
       - verdict 'must_pass': no forbidden_categories item may appear
  4. Write a verdict to reports/<scenario>.json.
  5. Exit non-zero if any scenario fails.

The runner does NOT call an LLM. The agent has already written the
review; this runner is the *check*, not the *reviewer*. Deterministic,
cheap, trust-clean.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _load_scenarios() -> list[dict]:
    return json.loads((HERE / "scenarios.json").read_text())["scenarios"]


def _score(review_text: str, expected: dict) -> tuple[bool, list[str]]:
    review_lower = review_text.lower()
    verdict = expected.get("verdict")
    if verdict == "must_flag":
        missing = [
            cat
            for cat in expected.get("required_categories", [])
            if cat.lower() not in review_lower
        ]
        return (len(missing) == 0, missing)
    if verdict == "must_pass":
        present = [
            cat
            for cat in expected.get("forbidden_categories", [])
            if cat.lower() in review_lower
        ]
        return (len(present) == 0, present)
    return (False, [f"unknown verdict: {verdict!r}"])


def run(reviews_dir: Path) -> int:
    scenarios = _load_scenarios()
    reports_dir = HERE / "reports"
    reports_dir.mkdir(exist_ok=True)
    failures = 0

    for sc in scenarios:
        name = sc["name"]
        expected_path = HERE / sc["expected"]
        expected = json.loads(expected_path.read_text())
        review_path = reviews_dir / f"{name}.txt"

        if not review_path.exists():
            problems = [f"no review found at {review_path}"]
            passed = False
        else:
            review_text = review_path.read_text()
            passed, problems = _score(review_text, expected)

        report = {
            "scenario": name,
            "verdict": "pass" if passed else "fail",
            "expected": expected,
            "review_path": str(review_path),
            "problems": problems,
        }
        (reports_dir / f"{name}.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )

        marker = "PASS" if passed else "FAIL"
        print(f"[{marker}] {name}")
        if not passed:
            for problem in problems:
                print(f"        - {problem}")
            failures += 1

    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Score agent-written reviews against bundled expectations. "
            "Run after the agent has written its reviews to "
            "evals/reviews/<scenario>.txt."
        )
    )
    parser.add_argument(
        "--reviews",
        default=str(HERE / "reviews"),
        help="Directory containing reviews named <scenario>.txt",
    )
    args = parser.parse_args()
    return run(Path(args.reviews))


if __name__ == "__main__":
    sys.exit(main())

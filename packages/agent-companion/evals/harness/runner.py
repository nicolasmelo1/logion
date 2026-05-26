"""End-to-end run: load scenarios + catalog, drive provider, grade, report."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from evals.harness.graders import Finding, grade
from evals.harness.providers.fake import FakeProvider
from evals.harness.schema import (
    Catalog,
    Scenario,
    Trace,
    load_catalog,
    load_scenarios_from_dir,
)


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    suite: str
    findings: tuple[Finding, ...]

    @property
    def passed(self) -> bool:
        return all(f.passed for f in self.findings)

    def failures(self) -> list[Finding]:
        return [f for f in self.findings if not f.passed]


METRIC_PROVIDER = "provider"


class Provider(Protocol):
    def run(self, scenario: Scenario, catalog: Catalog) -> Trace: ...


def run(
    scenarios_dir: Path,
    catalog_path: Path,
    *,
    provider: Provider | None = None,
) -> list[ScenarioResult]:
    catalog = load_catalog(catalog_path)
    scenarios = load_scenarios_from_dir(scenarios_dir)
    return run_scenarios(scenarios, catalog, provider=provider)


def run_scenarios(
    scenarios: list[Scenario],
    catalog: Catalog,
    *,
    provider: Provider | None = None,
) -> list[ScenarioResult]:
    prov = provider or FakeProvider()
    results: list[ScenarioResult] = []
    for scenario in scenarios:
        try:
            trace = prov.run(scenario, catalog)
        except Exception as exc:
            findings = [
                Finding.fail(
                    METRIC_PROVIDER,
                    "provider failed before grading: "
                    f"{type(exc).__name__}: {exc}",
                )
            ]
        else:
            findings = grade(scenario, trace, catalog)
        results.append(
            ScenarioResult(
                scenario_id=scenario.id,
                suite=scenario.suite,
                findings=tuple(findings),
            )
        )
    return results


def summarize(results: list[ScenarioResult]) -> dict[str, Any]:
    by_suite: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0}
    )
    by_metric: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0}
    )
    failures: list[dict[str, Any]] = []
    for result in results:
        bucket = by_suite[result.suite]
        bucket["total"] += 1
        bucket["passed" if result.passed else "failed"] += 1
        scenario_failures: list[dict[str, str]] = []
        # Aggregate findings per metric so a scenario contributes one
        # pass/fail per metric to by_metric, regardless of how many
        # findings a grader emitted (graders can emit multiple failure
        # messages for the same metric).
        metric_passed: dict[str, bool] = {}
        for finding in result.findings:
            prev = metric_passed.get(finding.metric, True)
            metric_passed[finding.metric] = prev and finding.passed
            if not finding.passed:
                scenario_failures.append({
                    "metric": finding.metric,
                    "message": finding.message,
                })
        for metric, passed in metric_passed.items():
            metric_bucket = by_metric[metric]
            metric_bucket["total"] += 1
            metric_bucket["passed" if passed else "failed"] += 1
        if scenario_failures:
            failures.append({
                "scenario_id": result.scenario_id,
                "suite": result.suite,
                "failures": scenario_failures,
            })
    totals = {
        "scenarios": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
    }
    return {
        "totals": totals,
        "by_suite": dict(by_suite),
        "by_metric": dict(by_metric),
        "failures": failures,
    }


def write_report(summary: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

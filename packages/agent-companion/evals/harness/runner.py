"""End-to-end run: load scenarios + catalog, drive provider, grade, report."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.harness.graders import Finding, grade
from evals.harness.providers.fake import FakeProvider
from evals.harness.schema import (
    Catalog,
    Scenario,
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


def run(
    scenarios_dir: Path,
    catalog_path: Path,
    *,
    provider: FakeProvider | None = None,
) -> list[ScenarioResult]:
    catalog = load_catalog(catalog_path)
    scenarios = load_scenarios_from_dir(scenarios_dir)
    return run_scenarios(scenarios, catalog, provider=provider)


def run_scenarios(
    scenarios: list[Scenario],
    catalog: Catalog,
    *,
    provider: FakeProvider | None = None,
) -> list[ScenarioResult]:
    prov = provider or FakeProvider()
    results: list[ScenarioResult] = []
    for scenario in scenarios:
        trace = prov.run(scenario, catalog)
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
        for finding in result.findings:
            metric_bucket = by_metric[finding.metric]
            metric_bucket["total"] += 1
            metric_bucket["passed" if finding.passed else "failed"] += 1
            if not finding.passed:
                scenario_failures.append({
                    "metric": finding.metric,
                    "message": finding.message,
                })
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

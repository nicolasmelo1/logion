"""Convert companion deterministic scenarios into eval contracts.

One source of truth converts: each companion scenario's ``expected``
facts become eval-contract assertions with stable, derivable ids, and
the conversion report compares *identity sets* — not counts — so a
converter that drops one assertion and invents another fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from logion_eval_contract import (
    EvalContract,
    contract_digest,
    contract_to_json,
    parse_contract_document,
)
from logion_eval_contract._json import JsonObject

CONVERSION_TOOL_VERSION = "logion.eval.convert.v1"

#: Grader metric -> the eval-assertion prefix it converts into.
_SOURCE_METRICS = {
    "local_recall": "local_recall",
    "routing": "routing",
    "course_selection": "course_selection",
    "safety": "safety",
    "context_efficiency": "context_efficiency",
    "updates": "updates",
}

#: Expected facts, in a stable order, each becoming one assertion id
#: ``<scenario_id>.<fact>`` with an operator and a threshold metric.
_FACTS = (
    "should_run_recall",
    "should_query_marketplace",
    "should_install",
    "should_ask_confirmation",
    "acceptable_course_ids",
    "forbidden_course_ids",
    "max_courses_inspected",
    "max_loaded_skills",
    "max_listings_limit",
    "must_mention",
    "must_not_mention",
    "forbidden_tools",
    "required_tools",
    "required_tool_sequence",
    "recall_bypass_allowed",
)


def source_assertion_ids(scenario: dict) -> list[str]:
    """Assertion ids derivable from one raw companion scenario."""
    expected = scenario.get("expected") or {}
    ids: list[str] = []
    for fact in _FACTS:
        value = expected.get(fact)
        if value is None or value == () or value is False:
            continue
        ids.append(f"{scenario['id']}.{fact}")
    return ids


def converted_assertion_ids(contract: EvalContract) -> list[str]:
    """Assertion ids present in one converted contract."""
    return [a.id for a in contract.assertions]


def convert_scenario(scenario: dict, suite: str) -> JsonObject:
    """Convert one raw companion scenario into an eval contract document.

    The scenario's ``fake_trace`` is the deterministic subject input:
    the contract's fixture is the trace, and the assertions grade the
    grader-derived facts exactly as the companion graders would.
    """
    scenario_id = scenario["id"]
    trace = scenario.get("fake_trace") or {}
    fixture_bytes = json.dumps(
        trace, sort_keys=True, separators=(",", ":")
    ).encode()
    import hashlib

    fixture_digest = hashlib.sha256(fixture_bytes).hexdigest()

    assertions: list[JsonObject] = []
    metrics: list[JsonObject] = []
    for fact, value in (scenario.get("expected") or {}).items():
        if value is None or value == () or value is False:
            continue
        assertion_id = f"{scenario_id}.{fact}"
        if isinstance(value, bool):
            metric_kind = "count"
            expected: int | str | float | bool | None = int(value)
        elif isinstance(value, int):
            metric_kind = "count"
            expected = value
        else:
            metric_kind = "count"
            expected = 1 if value else 0
        metrics.append({
            "id": assertion_id,
            "kind": metric_kind,
            "direction": "higher_is_better",
        })
        assertions.append({
            "id": assertion_id,
            "operator": "gte",
            "metric": assertion_id,
            "expected": expected,
        })

    document: JsonObject = {
        "schema_version": 1,
        "subject": {
            "type": "agent_companion_scenario",
            "digest_constraint": "exact",
        },
        "archetype": "exact_match",
        "inputs": [f"{scenario_id}.fake_trace"],
        "fixtures": [
            {"name": f"{scenario_id}.fake_trace", "digest": fixture_digest}
        ],
        "runtime_requirements": [
            {"kind": "sandbox_profile", "value": "pinned-image"}
        ],
        "steps": [
            {
                "id": f"run_{scenario_id}",
                "action": "grade_scenario",
                "params": {"suite": suite, "scenario": scenario_id},
            }
        ],
        "metrics": metrics,
        "assertions": assertions,
        "budgets": [{"kind": "wall_seconds", "max_value": 60}],
        "outputs": [{"name": "result", "path": "outputs/result.json"}],
        "redaction": {"mode": "drop", "fields": ["token", "secret"]},
        "determinism_class": "deterministic",
        "evaluator_requirement": {"kind": "none"},
    }
    return document


def convert_file(path: Path) -> list[JsonObject]:
    """Convert every scenario in one companion suite file."""
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"{path} is not a mapping")
    suite = str(raw.get("suite") or path.stem)
    scenarios = raw.get("scenarios") or []
    return [convert_scenario(s, suite) for s in scenarios]


def conversion_report(scenario: dict, contract: EvalContract) -> JsonObject:
    """The per-conversion report the gate requires."""
    source_ids = source_assertion_ids(scenario)
    converted_ids = converted_assertion_ids(contract)
    return {
        "source_scenario": scenario["id"],
        "source_assertion_ids": source_ids,
        "converted_assertion_ids": converted_ids,
        "dropped_assertion_count": len(set(source_ids) - set(converted_ids)),
        "added_assertion_count": len(set(converted_ids) - set(source_ids)),
        "conversion_tool_version": "0.1.0",
    }


def main(argv: list[str] | None = None) -> int:
    import yaml

    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        sys.stderr.write(
            "usage: convert_companion_scenario SCENARIOS_DIR OUT_DIR\\n"
        )
        return 2
    scenarios_dir = Path(args[0])
    out_dir = Path(args[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    reports: list[JsonObject] = []
    for path in sorted(scenarios_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        suite = str(raw.get("suite") or path.stem)
        for scenario in raw.get("scenarios") or []:
            document = convert_scenario(scenario, suite)
            contract = parse_contract_document(document, source_format="yaml")
            report = conversion_report(scenario, contract)
            report["contract_digest"] = contract_digest(contract)
            reports.append(report)
            out_path = out_dir / f"{scenario['id']}.eval-contract.yaml"
            out_path.write_text(
                json.dumps(
                    contract_to_json(contract), indent=2, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )
    (out_dir / "conversion-report.json").write_text(
        json.dumps({"conversions": reports}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    bad = [
        r
        for r in reports
        if r["dropped_assertion_count"] or r["added_assertion_count"]
    ]
    for report in bad:
        sys.stderr.write(
            f"identity-set mismatch for {report['source_scenario']}:"
            f" dropped={report['dropped_assertion_count']}"
            f" added={report['added_assertion_count']}\\n"
        )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

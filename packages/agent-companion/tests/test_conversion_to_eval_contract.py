"""Every companion deterministic scenario converts without losing
assertions: identity sets are compared, not counts."""

from __future__ import annotations

import json
from pathlib import Path

from evals.convert_to_eval_contract import (
    conversion_report,
    convert_scenario,
    converted_assertion_ids,
    source_assertion_ids,
)

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "evals" / "scenarios"


def _all_scenarios() -> list[tuple[str, dict]]:
    import yaml

    out: list[tuple[str, dict]] = []
    for path in sorted(SCENARIOS_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        suite = str(raw.get("suite") or path.stem)
        for scenario in raw.get("scenarios") or []:
            out.append((suite, scenario))
    return out


def test_every_scenario_converts_with_identical_assertion_sets() -> None:
    conversions = _all_scenarios()
    assert conversions, "companion scenarios must exist"
    mismatches: list[str] = []
    for suite, scenario in conversions:
        document = convert_scenario(scenario, suite)
        from logion_eval_contract import parse_contract_document

        contract = parse_contract_document(document, source_format="yaml")
        report = conversion_report(scenario, contract)
        if (
            report["dropped_assertion_count"]
            or report["added_assertion_count"]
        ):
            mismatches.append(
                f"{report['source_scenario']}: dropped="
                f"{report['dropped_assertion_count']} added="
                f"{report['added_assertion_count']}"
            )
    assert not mismatches, "\n".join(mismatches)


def test_converted_contracts_are_valid_and_deterministic() -> None:
    for suite, scenario in _all_scenarios():
        document = convert_scenario(scenario, suite)
        from logion_eval_contract import (
            contract_digest,
            parse_contract_document,
        )

        contract = parse_contract_document(document, source_format="yaml")
        assert contract.determinism_class == "deterministic"
        digest = contract_digest(contract)
        assert len(digest) == 64
        # Round-trip stability: the digest survives a JSON round-trip.
        reparsed = parse_contract_document(
            json.loads(json.dumps(document)), source_format="json"
        )
        assert contract_digest(reparsed) == digest


def test_source_ids_are_derivable_without_conversion() -> None:
    # The identity-set comparison is meaningful only if the source ids
    # derive from the scenario itself, not from the converted artifact.
    for _suite, scenario in _all_scenarios():
        ids = source_assertion_ids(scenario)
        expected = converted_assertion_ids(
            __import__("logion_eval_contract").parse_contract_document(
                convert_scenario(scenario, "suite"), source_format="yaml"
            )
        )
        assert sorted(ids) == sorted(expected)


def test_conversion_uses_closed_stable_fact_order() -> None:
    scenario = {
        "id": "stable",
        "fake_trace": {},
        "expected": {
            "required_tools": ["search"],
            "unsupported_fact": True,
            "should_run_recall": True,
        },
    }
    reversed_scenario = {
        **scenario,
        "expected": dict(reversed(list(scenario["expected"].items()))),
    }

    first = convert_scenario(scenario, "suite")
    second = convert_scenario(reversed_scenario, "suite")

    assert first == second
    assert [item["id"] for item in first["assertions"]] == [
        "stable.should_run_recall",
        "stable.required_tools",
    ]

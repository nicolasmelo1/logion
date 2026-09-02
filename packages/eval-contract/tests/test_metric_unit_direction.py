"""Metric kinds and directions are closed enums with units."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logion_eval_contract import parse_contract_document

FIXTURES = Path(__file__).parent / "fixtures"


def _payload() -> dict:
    return json.loads((FIXTURES / "golden_contract.json").read_text())


def test_unknown_metric_kind_rejected() -> None:
    payload = _payload()
    payload["metrics"][0]["kind"] = "score"
    with pytest.raises(ValueError, match="kind must be one of"):
        parse_contract_document(payload)


def test_unknown_direction_rejected() -> None:
    payload = _payload()
    payload["metrics"][0]["direction"] = "either"
    with pytest.raises(ValueError, match="direction must be one of"):
        parse_contract_document(payload)


def test_metric_unit_round_trips() -> None:
    payload = _payload()
    payload["metrics"][0]["unit"] = "cases"
    contract = parse_contract_document(payload)
    assert contract.metrics[0].unit == "cases"


def test_all_kinds_accepted() -> None:
    payload = _payload()
    kinds = ["count", "ratio", "duration_ms", "tokens", "cost_usd"]
    payload["metrics"] = [
        {"id": f"m{i}", "kind": k, "direction": "higher_is_better"}
        for i, k in enumerate(kinds)
    ]
    contract = parse_contract_document(payload)
    assert [m.kind for m in contract.metrics] == kinds

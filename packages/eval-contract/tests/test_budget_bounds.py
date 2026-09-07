"""Budget bounds: negative or malformed budgets fail closed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logion_eval_contract import parse_contract_document

FIXTURES = Path(__file__).parent / "fixtures"


def _payload() -> dict:
    return json.loads((FIXTURES / "golden_contract.json").read_text())


def test_negative_budget_rejected() -> None:
    payload = _payload()
    payload["budgets"][0]["max_value"] = -1
    with pytest.raises(ValueError, match="non-negative"):
        parse_contract_document(payload)


def test_boolean_budget_rejected() -> None:
    payload = _payload()
    payload["budgets"][0]["max_value"] = True
    with pytest.raises(ValueError, match="number"):
        parse_contract_document(payload)


def test_zero_budget_accepted() -> None:
    payload = _payload()
    payload["budgets"][0]["max_value"] = 0
    contract = parse_contract_document(payload)
    assert contract.budgets[0].max_value == 0


def test_large_budget_accepted() -> None:
    payload = _payload()
    payload["budgets"][0]["max_value"] = 3600
    contract = parse_contract_document(payload)
    assert contract.budgets[0].max_value == 3600

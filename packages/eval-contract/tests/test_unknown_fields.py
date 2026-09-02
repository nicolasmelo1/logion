"""Arbitrary top-level keys fail; extensions round-trip."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logion_eval_contract import (
    parse_contract_document,
    parse_result_document,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _contract_payload() -> dict:
    return json.loads((FIXTURES / "golden_contract.json").read_text())


def test_unknown_contract_field_rejected() -> None:
    payload = _contract_payload()
    payload["quality_score"] = 99
    with pytest.raises(ValueError, match="quality_score"):
        parse_contract_document(payload)


def test_extensions_are_accepted() -> None:
    payload = _contract_payload()
    payload["extensions"] = {"publisher_note": "ok"}
    contract = parse_contract_document(payload)
    assert contract.extensions == {"publisher_note": "ok"}


def test_unknown_result_field_rejected(minimal_result_payload: dict) -> None:
    payload = minimal_result_payload
    payload["quality_score"] = 99
    with pytest.raises(ValueError, match="quality_score"):
        parse_result_document(payload)


def test_result_extensions_accepted(minimal_result_payload: dict) -> None:
    payload = minimal_result_payload
    payload["extensions"] = {"note": "ok"}
    result = parse_result_document(payload)
    assert result.extensions == {"note": "ok"}


def test_extension_roundtrip_through_model() -> None:
    payload = _contract_payload()
    payload["extensions"] = {"tool": {"version": 2}}
    contract = parse_contract_document(payload)
    assert contract_to_json_extensions(contract) == {"tool": {"version": 2}}


def contract_to_json_extensions(contract: object) -> dict:
    from logion_eval_contract.parse import contract_to_json

    document = contract_to_json(contract)  # type: ignore[arg-type]
    return document.get("extensions", {})

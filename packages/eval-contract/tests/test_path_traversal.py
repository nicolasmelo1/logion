"""Output paths, fixture names, and inputs must not traverse."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logion_eval_contract import parse_contract_document

FIXTURES = Path(__file__).parent / "fixtures"


def _payload() -> dict:
    return json.loads((FIXTURES / "golden_contract.json").read_text())


def test_parent_traversal_in_output_path_rejected() -> None:
    payload = _payload()
    payload["outputs"][0]["path"] = "../etc/result.json"
    with pytest.raises(ValueError, match="traversal"):
        parse_contract_document(payload)


def test_home_relative_output_path_rejected() -> None:
    payload = _payload()
    payload["outputs"][0]["path"] = "~/result.json"
    with pytest.raises(ValueError, match="traversal"):
        parse_contract_document(payload)


def test_env_expansion_output_path_rejected() -> None:
    payload = _payload()
    payload["outputs"][0]["path"] = "$HOME/result.json"
    with pytest.raises(ValueError, match="traversal"):
        parse_contract_document(payload)


def test_clean_relative_path_accepted() -> None:
    payload = _payload()
    contract = parse_contract_document(payload)
    assert contract.outputs[0].path == "outputs/result.json"

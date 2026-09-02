"""Extensions survive document -> model -> document round-trips."""

from __future__ import annotations

import json
from pathlib import Path

from logion_eval_contract import (
    contract_digest,
    parse_contract_document,
    parse_result_document,
    result_digest,
    result_to_json,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_contract_extension_roundtrip() -> None:
    payload = json.loads((FIXTURES / "golden_contract.json").read_text())
    payload["extensions"] = {
        "publisher": {"name": "acme", "tier": 2},
        "tags": ["normalization"],
    }
    contract = parse_contract_document(payload)
    rebuilt = contract.to_json()
    assert rebuilt["extensions"] == payload["extensions"]
    # Extensions participate in the digest: two contracts differing
    # only in extensions have different digests.
    bare = parse_contract_document({
        **payload,
        "extensions": {},
    })
    assert contract_digest(contract) != contract_digest(bare)


def test_result_extension_roundtrip(minimal_result_payload: dict) -> None:
    payload = minimal_result_payload
    payload["extensions"] = {"driver": {"tokens": 512}}
    result = parse_result_document(payload)
    document = result_to_json(result)
    assert document["extensions"] == {"driver": {"tokens": 512}}
    assert result_digest(result) == result_digest(
        parse_result_document(document)
    )


def test_extensions_absent_means_empty() -> None:
    payload = json.loads((FIXTURES / "golden_contract.json").read_text())
    contract = parse_contract_document(payload)
    assert contract.extensions == {}
    assert "extensions" not in contract.to_json()

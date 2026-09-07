"""Canonicalization is JCS; digests agree across equivalent forms."""

from __future__ import annotations

from pathlib import Path

from logion_eval_contract import (
    canonicalize,
    canonicalize_text,
    contract_digest,
    is_round_trip_stable,
    parse_contract_document,
    short_sha256,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_canonical_output_is_sorted_compact() -> None:
    text = canonicalize_text({"b": 1, "a": [2, 1], "c": None})
    assert text == '{"a":[2,1],"b":1,"c":null}'


def test_canonical_round_trip_is_stable() -> None:
    payload = {"nested": {"z": 1, "a": [True, "x", 2.5]}}
    assert is_round_trip_stable(payload)


def test_short_sha256_is_lowercase_hex() -> None:
    digest = short_sha256({"k": "v"})
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_contract_digest_uses_jcs_bytes() -> None:
    doc, kind = load_document_json()
    contract = parse_contract_document(doc, source_format=kind)
    import hashlib

    from logion_eval_contract.parse import contract_to_json

    manual = hashlib.sha256(
        canonicalize(contract_to_json(contract))
    ).hexdigest()
    assert contract_digest(contract) == manual


def load_document_json() -> tuple[dict, str]:
    import json

    doc = json.loads((FIXTURES / "golden_contract.json").read_text())
    return doc, "json"

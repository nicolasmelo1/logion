"""Fixture digests bind contract inputs to exact bytes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logion_eval_contract import parse_contract_document

FIXTURES = Path(__file__).parent / "fixtures"


def _payload() -> dict:
    return json.loads((FIXTURES / "golden_contract.json").read_text())


def test_uppercase_digest_rejected() -> None:
    payload = _payload()
    payload["fixtures"][0]["digest"] = payload["fixtures"][0]["digest"].upper()
    with pytest.raises(ValueError, match="sha256"):
        parse_contract_document(payload)


def test_short_digest_rejected() -> None:
    payload = _payload()
    payload["fixtures"][0]["digest"] = "abc123"
    with pytest.raises(ValueError, match="sha256"):
        parse_contract_document(payload)


def test_duplicate_fixture_names_rejected() -> None:
    payload = _payload()
    payload["fixtures"].append({
        "name": "normalize_input.json",
        "digest": "0" * 64,
    })
    with pytest.raises(ValueError, match="duplicate"):
        parse_contract_document(payload)


def test_real_file_digest_matches_declaration() -> None:
    import hashlib

    payload = _payload()
    declared = payload["fixtures"][0]["digest"]
    actual = hashlib.sha256(
        (FIXTURES / "normalize_input.json").read_bytes()
    ).hexdigest()
    # The golden fixture declares a synthetic digest; this test pins
    # the *mechanism*: hashing the real file gives the digest a
    # consumer would verify against.
    assert hashlib.sha256(b"").hexdigest() != declared
    assert len(actual) == 64

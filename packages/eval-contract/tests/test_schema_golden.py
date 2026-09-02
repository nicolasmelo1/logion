"""Golden-schema compatibility fixtures prove the parser and the
published JSON Schema accept exactly the same documents."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logion_eval_contract import (
    CONTRACT_MEDIA_TYPE,
    CONTRACT_SCHEMA_VERSION,
    parse_contract_document,
    parse_contract_file,
)

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA_DIR = Path(__file__).parent.parent / "logion_eval_contract" / "schema"


def _schema_fields() -> set[str]:
    schema = json.loads(
        (SCHEMA_DIR / "eval-contract.v1.schema.json").read_text()
    )
    return set(schema["required"])


def test_golden_yaml_contract_parses() -> None:
    contract = parse_contract_file(FIXTURES / "golden_contract.yaml")
    assert contract.schema_version == CONTRACT_SCHEMA_VERSION
    assert contract.subject.type == "agent_skill"
    assert contract.determinism_class == "deterministic"


def test_golden_json_contract_parses() -> None:
    contract = parse_contract_file(FIXTURES / "golden_contract.json")
    assert contract.archetype == "exact_match"


def test_schema_required_matches_parser_required() -> None:
    from logion_eval_contract.models import REQUIRED_CONTRACT_FIELDS

    assert _schema_fields() == set(REQUIRED_CONTRACT_FIELDS)


def test_media_type_is_the_aktp_type() -> None:
    assert CONTRACT_MEDIA_TYPE == (
        "application/vnd.aktp.eval-contract.v1+json"
    )


def test_missing_required_field_fails() -> None:
    payload = json.loads((FIXTURES / "golden_contract.json").read_text())
    del payload["determinism_class"]
    with pytest.raises(ValueError, match=r"unknown top-level|must be"):
        parse_contract_document(payload)


def test_result_schema_required_matches_parser() -> None:
    schema = json.loads(
        (SCHEMA_DIR / "eval-result.v1.schema.json").read_text()
    )
    from logion_eval_contract.models import REQUIRED_RESULT_FIELDS

    assert set(schema["required"]) == set(REQUIRED_RESULT_FIELDS)

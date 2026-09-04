"""The YAML and JSON forms of one contract must produce one digest."""

from __future__ import annotations

from pathlib import Path

import pytest

from logion_eval_contract import (
    contract_digest,
    load_document,
    parse_contract_document,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("value", ["when: 2026-09-03", "value: .nan", "1: x"])
def test_load_document_rejects_yaml_only_shapes(
    tmp_path: Path, value: str
) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(value + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"JSON|finite|non-string"):
        load_document(path)


def test_yaml_and_json_forms_share_one_digest() -> None:
    yaml_doc, yaml_kind = load_document(FIXTURES / "golden_contract.yaml")
    json_doc, json_kind = load_document(FIXTURES / "golden_contract.json")
    assert yaml_kind == "yaml"
    assert json_kind == "json"
    yaml_contract = parse_contract_document(yaml_doc, source_format=yaml_kind)
    json_contract = parse_contract_document(json_doc, source_format=json_kind)
    assert contract_digest(yaml_contract) == contract_digest(json_contract)


def test_digest_is_stable_across_key_order() -> None:
    import copy

    doc, kind = load_document(FIXTURES / "golden_contract.json")
    reordered = copy.deepcopy(doc)
    # Rebuild with reversed key order; canonicalization sorts keys.
    reordered = dict(reversed(list(reordered.items())))
    contract = parse_contract_document(reordered, source_format=kind)
    original = parse_contract_document(doc, source_format=kind)
    assert contract_digest(contract) == contract_digest(original)

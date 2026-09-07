"""Golden-schema compatibility fixtures prove the parser and the
published JSON Schema accept exactly the same documents: every fixture
is validated against the published schema with ``jsonschema``, and
every mutation the parser rejects is rejected by the schema too (and
vice versa)."""

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
from logion_eval_contract.errors import EvalContractInvalid

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


def _contract_schema() -> dict:
    return json.loads(
        (SCHEMA_DIR / "eval-contract.v1.schema.json").read_text()
    )


def _result_schema() -> dict:
    return json.loads((SCHEMA_DIR / "eval-result.v1.schema.json").read_text())


def _golden_payload() -> dict:
    return json.loads((FIXTURES / "golden_contract.json").read_text())


def test_golden_contract_validates_against_the_published_schema() -> None:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(_contract_schema())

    errors = list(validator.iter_errors(_golden_payload()))

    assert errors == [], [e.message for e in errors]


def test_parser_rejections_are_schema_rejections() -> None:
    """A document either side rejects must be rejected by both."""
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(_contract_schema())

    mutations = [
        lambda p: p["metrics"][0].update({"bogus": 1}),
        lambda p: p["assertions"][0].update({"sneaky": True}),
        lambda p: p["budgets"][0].update({"x": 1}),
        lambda p: p["subject"].update({"extra": 1}),
        lambda p: p["outputs"][0].update({"path": "../etc/result.json"}),
        lambda p: p["fixtures"][0].update({"name": "../fixture.json"}),
        lambda p: p.update({"inputs": ["$HOME/input.json"]}),
        lambda p: p["metrics"][0].update({"kind": "not-a-kind"}),
        lambda p: p["assertions"][0].update({"operator": "=>"}),
        lambda p: p.update({"determinism_class": "random"}),
        lambda p: p.update({"quality_score": 99}),
    ]

    for mutate in mutations:
        payload = _golden_payload()
        mutate(payload)
        with pytest.raises(EvalContractInvalid):
            parse_contract_document(json.loads(json.dumps(payload)))
        schema_errors = list(validator.iter_errors(payload))
        assert schema_errors != [], (
            f"parser rejects, schema accepts: {payload}"
        )


def test_parser_accepts_what_the_schema_accepts() -> None:
    """Symmetric probe on a valid variant: both sides accept."""
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(_contract_schema())

    payload = _golden_payload()
    payload["extensions"] = {"note": "ok"}

    assert list(validator.iter_errors(payload)) == []
    parse_contract_document(json.loads(json.dumps(payload)))


def test_schema_and_parser_accept_benign_path_characters() -> None:
    from jsonschema import Draft202012Validator

    payload = _golden_payload()
    payload["outputs"][0]["path"] = "outputs/cost$~..json"

    assert (
        list(Draft202012Validator(_contract_schema()).iter_errors(payload))
        == []
    )
    parse_contract_document(payload)


def test_the_result_schema_rejects_the_parser_rejections() -> None:
    """Result-side parity: unknown environment keys fail both sides."""
    from jsonschema import Draft202012Validator

    from logion_eval_contract import parse_result_document

    validator = Draft202012Validator(_result_schema())
    result = _result_payload()
    result["environment"]["region"] = "us-east-1"

    with pytest.raises(ValueError, match="unknown keys"):
        parse_result_document(result)

    assert list(validator.iter_errors(result)) != []


def _result_payload() -> dict:
    """The conftest result fixture, imported as a plain function.

    The shared fixture lives in ``tests/conftest.py`` (no ``__init__``
    by convention); importing a bare ``conftest`` module is
    cross-package poison in root pytest runs, so build the minimal
    result inline from the same fixture file the golden digest uses.
    """
    from logion_eval_contract import (
        contract_digest,
        environment_digest_from,
        parse_contract_document,
    )

    environment_digest = environment_digest_from(
        harness_id="logion-node",
        harness_version="0.1.0",
        model_id="fixture-model",
        model_version="1",
    )
    contract_digest_value = contract_digest(
        parse_contract_document(_golden_payload())
    )
    return {
        "contract_digest": contract_digest_value,
        "subject_digest": "a" * 64,
        "environment": {
            "harness_id": "logion-node",
            "harness_version": "0.1.0",
            "model_id": "fixture-model",
            "model_version": "1",
        },
        "environment_digest": environment_digest,
        "assertion_vector": [
            {
                "id": "output_matches_golden",
                "operator": "eq",
                "passed": True,
                "actual": 1,
            }
        ],
        "metrics": [
            {
                "id": "cases_passed",
                "kind": "count",
                "direction": "higher_is_better",
                "value": 1,
            }
        ],
        "outcome": "passed",
        "artifacts": {},
        "resource_usage": {},
        "limitations": "Fixture run; no external validity.",
        "contract_standing": "unreviewed",
    }


def test_the_result_schema_accepts_the_honest_result() -> None:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(_result_schema())

    payload = _result_payload()

    assert list(validator.iter_errors(payload)) == [], [
        e.message for e in validator.iter_errors(payload)
    ]

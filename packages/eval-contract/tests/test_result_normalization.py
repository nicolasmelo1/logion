"""A third party validates using only this package and the fixtures."""

from __future__ import annotations

from pathlib import Path

from logion_eval_contract import (
    parse_result_document,
    result_digest,
    result_to_json,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _env_digest(base_env: dict, **overrides: str) -> str:
    import hashlib
    import json

    env = {**base_env, **overrides}
    return hashlib.sha256(
        json.dumps(env, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_minimal_result_document_parses(
    minimal_result_payload: dict,
) -> None:
    payload = minimal_result_payload
    result = parse_result_document(payload)
    assert result.outcome == "passed"
    assert result.contract_standing == "unreviewed"


def test_result_digest_is_stable(minimal_result_payload: dict) -> None:
    payload = minimal_result_payload
    first = result_digest(parse_result_document(payload))
    second = result_digest(parse_result_document(payload))
    assert first == second


def test_environment_digest_is_closed_over_named_fields(
    minimal_result_payload: dict,
) -> None:
    payload = minimal_result_payload
    result = parse_result_document(payload)
    changed_model = parse_result_document({
        **payload,
        "environment": {**payload["environment"], "model_id": "other"},
        "environment_digest": _env_digest(
            payload["environment"], model_id="other"
        ),
    })
    assert result.environment_digest() != changed_model.environment_digest()


def test_limitations_prose_cannot_change_the_pair_digest(
    minimal_result_payload: dict,
) -> None:
    payload = minimal_result_payload
    result = parse_result_document(payload)
    amended = parse_result_document({
        **payload,
        "limitations": "different prose",
    })
    assert result.environment_digest() == amended.environment_digest()


def test_compare_requires_same_pair(minimal_result_payload: dict) -> None:
    from logion_eval_contract.normalize import pair_key

    payload = minimal_result_payload
    base = parse_result_document(payload)
    same = parse_result_document(payload)
    other = parse_result_document({
        **payload,
        "environment": {
            **payload["environment"],
            "harness_id": "other-harness",
        },
        "environment_digest": _env_digest(
            payload["environment"], harness_id="other-harness"
        ),
    })
    assert pair_key(base) == pair_key(same)
    assert pair_key(base) != pair_key(other)


def test_result_to_json_roundtrip_is_byte_stable(
    minimal_result_payload: dict,
) -> None:
    payload = minimal_result_payload
    first = result_to_json(parse_result_document(payload))
    second = result_to_json(parse_result_document(first))
    import json

    assert json.dumps(first, sort_keys=True) == json.dumps(
        second, sort_keys=True
    )

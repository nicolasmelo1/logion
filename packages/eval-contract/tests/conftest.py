"""Shared result fixture builder, exposed via conftest.

The public-package test-dir convention forbids ``__init__.py`` (root
``pytest packages/`` collection collides on package names), so the
helper lives in ``conftest.py`` and tests receive it as a fixture.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

CONTRACT_FILE = FIXTURES / "golden_contract.json"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def golden_contract_digest() -> str:
    from logion_eval_contract.parse import (
        contract_digest,
        load_document,
        parse_contract_document,
    )

    doc, kind = load_document(CONTRACT_FILE)
    return contract_digest(parse_contract_document(doc, source_format=kind))


def subject_digest() -> str:
    return sha256_of(FIXTURES / "normalize_input.json")


def minimal_result(
    harness_id: str = "logion-node",
    model_id: str = "fixture-model",
) -> dict:
    """A valid, complete result document for the golden contract."""
    environment_digest = hashlib.sha256(
        json.dumps(
            {
                "harness_id": harness_id,
                "harness_version": "0.1.0",
                "model_id": model_id,
                "model_version": "1",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return {
        "contract_digest": golden_contract_digest(),
        "subject_digest": subject_digest(),
        "environment": {
            "harness_id": harness_id,
            "harness_version": "0.1.0",
            "model_id": model_id,
            "model_version": "1",
        },
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
        "environment_digest": environment_digest,
        "contract_standing": "unreviewed",
    }


@pytest.fixture
def minimal_result_payload() -> dict:
    return minimal_result()

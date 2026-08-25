# SPDX-License-Identifier: MIT
"""The generated client must not soften the contract.

`--allow-extra-fields` makes datamodel-codegen mark every model
`extra="allow"`, including request bodies the contract declares closed.
A third party reading the generated client then concludes the boundary is
open when the server rejects the field with a 422.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from logion.v1._types.generated import v1

SPEC = (
    Path(__file__).resolve().parents[3] / "contracts" / "openapi" / "v1.json"
)


def _closed_request_models() -> set[str]:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    schemas = spec.get("components", {}).get("schemas", {})
    closed: set[str] = set()
    for operations in spec.get("paths", {}).values():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            body = operation.get("requestBody") or {}
            for media in (body.get("content") or {}).values():
                ref = (media.get("schema") or {}).get("$ref", "")
                if not ref.startswith("#/components/schemas/"):
                    continue
                name = ref.rsplit("/", 1)[1]
                if schemas.get(name, {}).get("additionalProperties") is False:
                    closed.add(name)
    return closed


def test_contract_still_closes_at_least_one_request_body() -> None:
    """Guard the guard: an empty set would make the test below vacuous."""
    assert _closed_request_models()


@pytest.mark.parametrize("name", sorted(_closed_request_models()))
def test_closed_request_model_forbids_extra_fields(name: str) -> None:
    model = getattr(v1, name)
    assert model.model_config.get("extra") == "forbid", (
        f"{name} is additionalProperties:false in the contract but the "
        f"generated client accepts unknown fields"
    )


def test_submit_usage_receipt_rejects_an_upstream_reference() -> None:
    """The concrete case: no evidence reference on the usage receipt.

    ASM asked whether an optional `{kind, digest, issuer}` could ride on
    this request. The contract says no; this proves the generated client
    says no in the same place, rather than sending a field the server 422s.
    """
    with pytest.raises(ValidationError):
        v1.SubmitUsageReceiptRequest(
            observation_id="00000000-0000-0000-0000-000000000000",
            acquisition_channel="npx_skills",
            task_class="coding",
            consent_policy_digest="sha256:0",
            upstream_evidence={"kind": "asm.selection_receipt"},
        )

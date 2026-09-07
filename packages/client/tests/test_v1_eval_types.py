# SPDX-License-Identifier: MIT
"""Public eval SDK type exports."""

from logion.v1 import (
    EvalErrorResponse,
    SubmitEvalResultRequest,
    SubmitEvalResultResponse,
    UploadEvalContractRequest,
    UploadEvalContractResponse,
    ValidateEvalJobRequest,
    ValidateEvalJobResponse,
)


def test_eval_api_types_are_public() -> None:
    assert UploadEvalContractRequest(document={}).document == {}
    assert UploadEvalContractResponse(
        contract_digest="a" * 64,
        created=True,
        media_type="application/json",
    ).created
    assert (
        ValidateEvalJobRequest(
            contract_ref="contract",
            subject_digest="b" * 64,
            fixture_digests={},
        ).contract_ref
        == "contract"
    )
    assert ValidateEvalJobResponse(contract_digest="a" * 64, valid=True).valid
    assert SubmitEvalResultRequest(result={}).result == {}
    assert (
        SubmitEvalResultResponse(
            created=True, result_digest="c" * 64, run_id="run"
        ).run_id
        == "run"
    )
    assert EvalErrorResponse(detail="invalid").detail == "invalid"

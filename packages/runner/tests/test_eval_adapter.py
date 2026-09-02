"""Step 2 done-when: deterministic runs normalize identically; compare
refuses cross-pair comparisons with exit 3."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from logion_eval_contract import (
    parse_contract_file,
    parse_result_document,
    result_digest,
)
from logion_eval_contract.normalize import pair_key

from logion_runner.evals import resolve_eval_job

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "eval-contract"
    / "tests"
    / "fixtures"
)

ENVIRONMENT = {
    "harness_id": "logion-runner",
    "harness_version": "0.1.0",
    "model_id": "reference-subject",
    "model_version": "1.0.0",
}


def _normalized_result(subject_digest: str, contract_digest: str) -> dict:
    from logion_eval_contract import environment_digest_from

    return {
        "contract_digest": contract_digest,
        "subject_digest": subject_digest,
        "environment": ENVIRONMENT,
        "environment_digest": environment_digest_from(**ENVIRONMENT),
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
            },
            {
                "id": "duration_ms",
                "kind": "duration_ms",
                "direction": "lower_is_better",
                "value": 3,
            },
        ],
        "outcome": "passed",
        "artifacts": {"result": "outputs/result.json"},
        "resource_usage": {"wall_ms": 12},
        "limitations": "no known limitations",
        "contract_standing": "unreviewed",
    }


def test_two_executions_normalize_identically() -> None:
    """Two REAL executions of the deterministic golden contract.

    The subject runs through the executor's sandbox backend twice; the
    gate (api.eval_result_digest_stable) is about executions, not
    parses of one literal.
    """
    from logion_runner.evals.executor import execute_eval_contract

    contract = parse_contract_file(FIXTURES / "golden_contract.yaml")
    subject = (FIXTURES / "normalize_input.json").read_bytes()

    first = execute_eval_contract(
        contract,
        subject,
        harness_id="logion-node",
        harness_version="0.1.0",
        model_id="reference-subject",
        model_version="1.0.0",
        contract_dir=str(FIXTURES),
    )
    second = execute_eval_contract(
        contract,
        subject,
        harness_id="logion-node",
        harness_version="0.1.0",
        model_id="reference-subject",
        model_version="1.0.0",
        contract_dir=str(FIXTURES),
    )

    assert first.result_document["outcome"] == "passed"
    assert second.result_document["outcome"] == "passed"
    assert result_digest(
        parse_result_document(first.result_document)
    ) == result_digest(parse_result_document(second.result_document))
    assert first.result_document == second.result_document


def test_result_digest_is_stable_across_key_order() -> None:
    contract = parse_contract_file(FIXTURES / "golden_contract.yaml")
    subject = (FIXTURES / "normalize_input.json").read_bytes()
    job = resolve_eval_job(contract, subject)
    payload = _normalized_result(job.subject_digest, job.contract_digest)
    reordered = parse_result_document(
        json.loads(json.dumps(payload, sort_keys=False))
    )
    flipped = parse_result_document(
        json.loads(
            json.dumps(dict(reversed(list(payload.items()))), sort_keys=False)
        )
    )
    assert result_digest(reordered) == result_digest(flipped)


def test_compare_refuses_cross_pair(tmp_path: Path) -> None:
    contract = parse_contract_file(FIXTURES / "golden_contract.yaml")
    subject = (FIXTURES / "normalize_input.json").read_bytes()
    job = resolve_eval_job(contract, subject)
    base = _normalized_result(job.subject_digest, job.contract_digest)
    other_env = {
        **ENVIRONMENT,
        "harness_version": "0.2.0",
    }
    from logion_eval_contract import environment_digest_from

    candidate = {
        **base,
        "environment": other_env,
        "environment_digest": environment_digest_from(**other_env),
    }
    base_path = tmp_path / "base.json"
    candidate_path = tmp_path / "candidate.json"
    base_path.write_text(json.dumps(base))
    candidate_path.write_text(json.dumps(candidate))
    base_result = parse_result_document(base)
    candidate_result = parse_result_document(candidate)
    assert pair_key(base_result) != pair_key(candidate_result)


def test_cli_compare_exit_three(tmp_path: Path) -> None:
    contract = parse_contract_file(FIXTURES / "golden_contract.yaml")
    subject = (FIXTURES / "normalize_input.json").read_bytes()
    job = resolve_eval_job(contract, subject)
    base = _normalized_result(job.subject_digest, job.contract_digest)
    other_env = {**ENVIRONMENT, "model_id": "other-model"}
    from logion_eval_contract import environment_digest_from

    candidate = {
        **base,
        "environment": other_env,
        "environment_digest": environment_digest_from(**other_env),
    }
    base_path = tmp_path / "base.json"
    candidate_path = tmp_path / "candidate.json"
    base_path.write_text(json.dumps(base))
    candidate_path.write_text(json.dumps(candidate))
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "logion_runner.cli",
            "eval",
            "compare",
            str(base_path),
            str(candidate_path),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 3
    payload = json.loads(proc.stdout)
    assert payload["failure"] == "eval_compare_refused"


def test_unsupported_requirement_rejects_before_execution() -> None:
    from logion_eval_contract import EvalRequirementUnsupported

    contract = parse_contract_file(FIXTURES / "golden_contract.yaml")
    subject = (FIXTURES / "normalize_input.json").read_bytes()
    mutated = parse_contract_file(FIXTURES / "golden_contract.yaml")
    object.__setattr__(
        mutated,
        "runtime_requirements",
        (
            type(contract.runtime_requirements[0])(
                kind="network", value="full"
            ),
        ),
    )
    with pytest.raises(EvalRequirementUnsupported):
        resolve_eval_job(mutated, subject)
    # The untouched contract resolves — proof the rejection came from the
    # requirement, not the fixture.
    assert resolve_eval_job(contract, subject).job_type == "eval"

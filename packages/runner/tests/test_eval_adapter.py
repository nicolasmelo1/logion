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


def test_pair_key_distinguishes_cross_pair() -> None:
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
    base_result = parse_result_document(base)
    candidate_result = parse_result_document(candidate)
    assert pair_key(base_result) != pair_key(candidate_result)


def test_executor_honors_all_sandbox_budgets() -> None:
    from logion_eval_contract import parse_contract_document

    from logion_runner.evals.executor import _limits_for

    document = json.loads((FIXTURES / "golden_contract.json").read_text())
    document["budgets"] = [
        {"kind": "wall_seconds", "max_value": 1},
        {"kind": "memory_bytes", "max_value": 2},
        {"kind": "output_bytes", "max_value": 3},
        {"kind": "log_bytes", "max_value": 4},
    ]
    contract = parse_contract_document(document)

    assert _limits_for(contract) == {
        "wall_seconds": 1,
        "memory_bytes": 2,
        "output_bytes": 3,
        "log_bytes": 4,
    }


@pytest.mark.parametrize("raw", [b"not json", b"[]", b"\xff"])
def test_executor_rejects_invalid_json_objects(raw: bytes) -> None:
    from logion_runner.evals.executor import EvalExecutionError, _json_object

    with pytest.raises(EvalExecutionError):
        _json_object(raw, "subject")


def test_executor_honors_declared_output_path_and_artifact_name() -> None:
    from logion_eval_contract import parse_contract_document

    from logion_runner.evals.executor import execute_eval_contract

    document = json.loads((FIXTURES / "golden_contract.json").read_text())
    document["outputs"] = [{"name": "graded", "path": "custom/result.json"}]
    contract = parse_contract_document(document)
    outcome = execute_eval_contract(
        contract,
        (FIXTURES / "normalize_input.json").read_bytes(),
        harness_id="logion-node",
        harness_version="0.1.0",
        model_id="reference-subject",
        model_version="1.0.0",
        contract_dir=FIXTURES,
    )

    assert outcome.result_document["artifacts"] == {
        "graded": "custom/result.json"
    }


def test_executor_rejects_unknown_metric() -> None:
    from logion_eval_contract import parse_contract_document

    from logion_runner.evals.executor import (
        EvalExecutionError,
        execute_eval_contract,
    )

    document = json.loads((FIXTURES / "golden_contract.json").read_text())
    document["metrics"][0]["id"] = "unknown_metric"
    document["assertions"][0]["metric"] = "unknown_metric"
    contract = parse_contract_document(document)

    with pytest.raises(EvalExecutionError, match="no evaluator"):
        execute_eval_contract(
            contract,
            (FIXTURES / "normalize_input.json").read_bytes(),
            harness_id="logion-node",
            harness_version="0.1.0",
            model_id="reference-subject",
            model_version="1.0.0",
            contract_dir=FIXTURES,
        )


def test_resource_execution_fails_closed_until_bytes_are_available() -> None:
    from argparse import Namespace

    from logion_runner.evals.cli import _subject_bytes

    with pytest.raises(OSError, match="resource content retrieval"):
        _subject_bytes(Namespace(resource="resource/id", subject=None))


def test_reference_subject_casefolds_email_values(tmp_path: Path) -> None:
    from logion_runner.job_payload import _run_eval_normalize

    payload = {
        "entrypoint": "normalize",
        "subject": {"input": {"email": " STRAßE@EXAMPLE.DE "}},
        "output_path": "custom/result.json",
    }

    assert _run_eval_normalize(payload, tmp_path) == 0
    result = json.loads((tmp_path / "custom/result.json").read_text())
    assert result["normalized"]["email"] == "strasse@example.de"


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

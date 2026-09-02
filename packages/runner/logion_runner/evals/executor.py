"""Execute an eval contract's subject and grade the observed outputs.

The execution reuses the runner's own sandbox backends: the subject
runs exactly the way a coordinator-leased job would run, and the
evaluator grades what the subject actually produced — never what it
intended. A contract step whose action has no executor fails closed
before any lease exists.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from logion_eval_contract import (
    EvalContract,
    JsonObject,
    ResultEnvironment,
)
from logion_eval_contract.models import AssertionOutcome, MetricValue

from logion_runner.evals import (
    ResolvedEvalJob,
    normalize_outcome,
    resolve_eval_job,
)
from logion_runner.sandbox.backends import (
    ExecutionResult,
    LocalTestBackend,
)


class EvalExecutionError(RuntimeError):
    """The contract declares work no executor can perform."""


#: Job type the payload process executes for the reference subject.
EVAL_SUBJECT_JOB_TYPE = "eval_normalize"

#: Contract actions this executor knows. Anything else fails closed.
SUPPORTED_ACTIONS = ("execute_subject",)


@dataclass(frozen=True)
class GradedOutcome:
    """The graded, normalized result of one contract execution."""

    result_document: JsonObject
    assertion_outcomes: dict[str, bool]
    wall_ms: int


class SubjectRunner(Protocol):
    """The sandbox surface the executor needs."""

    def execute(
        self, lease: object, payload: JsonObject, *, on_heartbeat=None
    ) -> ExecutionResult: ...


def _unsupported_step(contract: EvalContract) -> str | None:
    for step in contract.steps:
        if step.action not in SUPPORTED_ACTIONS:
            return step.action
    return None


def _limits_for(contract: EvalContract) -> dict[str, int]:
    """The sandbox limits the contract's budgets pin."""
    limits = {
        "wall_seconds": 30,
        "memory_bytes": 536870912,
        "output_bytes": 1048576,
        "log_bytes": 65536,
    }
    for budget in contract.budgets:
        if budget.kind == "wall_seconds":
            limits["wall_seconds"] = int(budget.max_value)
        if budget.kind == "output_bytes":
            limits["output_bytes"] = int(budget.max_value)
    return limits


def _assertion_holds(
    operator: str, expected: object, observed: object
) -> bool:
    if operator == "eq":
        return observed == expected
    if operator == "ne":
        return observed != expected
    if isinstance(observed, str) and isinstance(expected, str):
        if operator == "contains":
            return expected in observed
        if operator == "matches":
            return re.search(expected, observed) is not None
    if (
        operator in ("lt", "lte", "gt", "gte")
        and isinstance(observed, (int, float))
        and isinstance(expected, (int, float))
    ):
        if operator == "lt":
            return observed < expected
        if operator == "lte":
            return observed <= expected
        if operator == "gt":
            return observed > expected
        return observed >= expected
    raise ValueError(
        f"operator {operator!r} not applicable to the observation"
    )


def _scalarize(observed: object) -> str | int | float | bool | None:
    if isinstance(observed, (str, int, float, bool)) or observed is None:
        return observed
    return json.dumps(observed, sort_keys=True)


def _metric_observation(
    metric_id: str,
    observed_document: JsonObject,
    wall_ms: int,
) -> int:
    """The observed value for one contract metric definition."""
    if metric_id == "cases_passed":
        normalized = observed_document.get("normalized")
        expected = observed_document.get("expected")
        expected_output = (
            expected.get("input") if isinstance(expected, dict) else None
        )
        return int(normalized == expected_output)
    if metric_id == "duration_ms":
        return wall_ms
    return 0


def execute_eval_contract(
    contract: EvalContract,
    subject_bytes: bytes,
    *,
    harness_id: str,
    harness_version: str,
    model_id: str,
    model_version: str,
    contract_dir: str | Path | None = None,
) -> GradedOutcome:
    """Run every step, grade the outputs, normalize the result.

    The subject's bytes are hashed exactly as a lease would bind them
    (``subject_digest_for``), the declared step executes inside the
    local-test sandbox backend, and the graded outcome is normalized by
    the adapter so the published result is byte-identical to what a
    coordinator-leased run would publish.
    """
    unsupported = _unsupported_step(contract)
    if unsupported is not None:
        raise EvalExecutionError(
            f"no executor for contract step action {unsupported!r}"
        )

    job = resolve_eval_job(contract, subject_bytes, contract_dir=contract_dir)

    subject_document = json.loads(subject_bytes.decode("utf-8"))
    payload: JsonObject = {
        "job_type": EVAL_SUBJECT_JOB_TYPE,
        "entrypoint": (
            contract.steps[0].params.get("entrypoint")
            if contract.steps
            else "normalize"
        ),
        "subject": {
            "input": subject_document.get("input"),
            "expected": subject_document.get("expected"),
        },
    }

    limits = _limits_for(contract)
    from logion_runner.job import JobLimits, Lease

    lease = Lease(
        job_id=f"eval-{job.idempotency_key}",
        attempt=1,
        job_type=EVAL_SUBJECT_JOB_TYPE,
        contract_digest=job.contract_digest,
        sandbox_profile=dict(job.sandbox_profile),
        sandbox_profile_digest=job.sandbox_profile_digest,
        resource_id="local",
        resource_version_id="local",
        resource_digest=job.subject_digest,
        required_capabilities=[],
        input_digests=job.input_digests,
        limits=JobLimits(
            wall_seconds=limits["wall_seconds"],
            memory_bytes=limits["memory_bytes"],
            output_bytes=limits["output_bytes"],
            log_bytes=limits["log_bytes"],
        ),
        artifacts=[],
        idempotency_key=job.idempotency_key,
        lease_expires_at="",
    )

    started = time.monotonic()
    backend = LocalTestBackend(python_executable=sys.executable)
    execution = backend.execute(lease, payload)
    wall_ms = int((time.monotonic() - started) * 1000)

    if execution.status == "timed_out":
        raise EvalExecutionError(
            "subject execution exceeded the contract's wall budget"
        )
    if execution.status != "succeeded":
        raise EvalExecutionError(
            "subject execution failed:"
            f" exit={execution.exit_code} stderr={execution.stderr[:200]}"
        )

    return _grade(
        contract,
        job,
        execution,
        wall_ms,
        ResultEnvironment(
            harness_id=harness_id,
            harness_version=harness_version,
            model_id=model_id,
            model_version=model_version,
        ),
    )


def _grade(
    contract: EvalContract,
    job: ResolvedEvalJob,
    execution: ExecutionResult,
    wall_ms: int,
    environment: ResultEnvironment,
) -> GradedOutcome:
    """Grade observed outputs against the contract's assertions."""
    output_path = contract.outputs[0].path if contract.outputs else None
    if output_path is None:
        raise EvalExecutionError("contract declares no outputs to grade")
    raw = execution.output_files.get(output_path)
    if raw is None:
        raise EvalExecutionError(
            f"subject produced no output at {output_path!r}"
        )
    observed_document = json.loads(raw.decode("utf-8"))

    metrics_by_id = {
        metric.id: MetricValue(
            id=metric.id,
            kind=metric.kind,
            direction=metric.direction,
            value=_metric_observation(metric.id, observed_document, wall_ms),
        )
        for metric in contract.metrics
    }

    outcomes: list[AssertionOutcome] = []
    for assertion in contract.assertions:
        observed: object
        if assertion.metric in metrics_by_id:
            observed = metrics_by_id[assertion.metric].value
        else:
            observed = _scalarize(observed_document.get(assertion.metric))
        holds = _assertion_holds(
            assertion.operator, assertion.expected, observed
        )
        outcomes.append(
            AssertionOutcome(
                id=assertion.id,
                operator=assertion.operator,
                passed=holds,
                actual=_scalarize(observed),
            )
        )

    outcome = "passed" if all(o.passed for o in outcomes) else "failed"
    result = normalize_outcome(
        contract,
        job.subject_digest,
        environment,
        tuple(outcomes),
        tuple(metrics_by_id.values()),
        outcome,
        {name: f"outputs/{name}" for name in execution.output_files},
        {"wall_ms": wall_ms},
        "no known limitations",
    )
    return GradedOutcome(
        result_document=result.to_json(),
        assertion_outcomes={o.id: o.passed for o in outcomes},
        wall_ms=wall_ms,
    )

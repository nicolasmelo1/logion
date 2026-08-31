"""The lease loop: claim, execute, upload, attest.

``run_one_iteration`` performs one full pass:

1. lease a job (or discover the queue is empty);
2. heartbeat to confirm the lease and learn of any cancel intent;
3. execute the payload inside the configured sandbox backend;
4. upload every output artifact;
5. build and sign the receipt, then submit it.

Every failure mode lands in one of the declared terminal states:
wall clock exceeded -> ``timed_out``; execution error -> ``failed``;
a blocked forbidden effect -> ``failed`` with the effect fields inside
the receipt; heartbeat ``cancel_requested`` -> ``cancelled``.
"""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Protocol

from logion_runner._jcs import short_sha256
from logion_runner._json import JsonObject
from logion_runner.coordinator_client import (
    CoordinatorClient,
    CoordinatorError,
)
from logion_runner.job import Lease
from logion_runner.receipt_builder import (
    SIGNATURE_ALGORITHM,
    ExecutionOutcome,
    ReceiptInput,
    build_receipt,
    sign_receipt,
    utc_now_iso,
)
from logion_runner.sandbox.backends import (
    ExecutionResult,
    SandboxBackend,
    SandboxExecutionError,
    SandboxUnavailable,
)


class StateStore(Protocol):
    """Where the loop records local run history (CLI ``jobs``)."""

    def record(self, entry: JsonObject) -> None: ...


class JsonlStateStore:
    """Append-only JSONL run history inside the state directory."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def record(self, entry: JsonObject) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"recorded_at": utc_now_iso(), **entry}
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")


class LoopError(RuntimeError):
    """The lease loop cannot continue safely (credential/lease loss)."""


class LeaseLost(LoopError):
    """The coordinator rejected the heartbeat with 409 lease_lost."""


def run_loop(
    client: CoordinatorClient,
    backend: SandboxBackend,
    *,
    runner_id: str,
    runner_key: str,
    signing_key,
    capabilities: list[str],
    runtime_digest: str,
    poll_seconds: int,
    stop,
    state_store: StateStore | None = None,
) -> int:
    """Poll until ``stop`` is true, returning the number of iterations."""
    iterations = 0
    while not stop():
        run_one_iteration(
            client,
            backend,
            runner_id=runner_id,
            runner_key=runner_key,
            signing_key=signing_key,
            capabilities=capabilities,
            runtime_digest=runtime_digest,
            state_store=state_store,
        )
        iterations += 1
        if not stop():
            time.sleep(max(0, poll_seconds))
    return iterations


def _assertion_vector_digest(result: ExecutionResult) -> str:
    """Digest over the machine-checkable outcome facts of one attempt."""
    vector = {
        "exit_code": result.exit_code,
        "output_digests": result.output_digests,
        "status": result.status,
        "truncated_output": result.truncated_output,
    }
    return short_sha256(vector)


def _payload_for(lease: Lease) -> JsonObject:
    """Build the sandbox payload file's content for *lease*.

    The payload is intentionally small and serializable: job type,
    declared inputs, and where to write outputs. Nothing from the host
    environment flows in.
    """
    return {
        "job_id": lease.job_id,
        "attempt": lease.attempt,
        "job_type": lease.job_type,
        "contract_digest": lease.contract_digest,
        "resource_id": lease.resource_id,
        "resource_version_id": lease.resource_version_id,
        "input_digests": lease.input_digests,
        "fixture": lease.fixture,
        "effect": lease.effect,
        "sandbox_profile": lease.sandbox_profile,
    }


def _leased_summary(
    lease: Lease,
    status: str,
    *,
    artifacts: dict[str, str] | None = None,
    duplicate_rejected: bool = False,
    coordinator_accepted: bool = True,
    coordinator_facts: JsonObject | None = None,
) -> JsonObject:
    summary: JsonObject = {
        "leased": True,
        "job_id": lease.job_id,
        "status": status,
        "attempt": lease.attempt,
    }
    if coordinator_facts:
        for key in ("attempt_count", "terminal_transition_count"):
            if key in coordinator_facts:
                summary[key] = coordinator_facts[key]
    if artifacts is not None:
        receipt_summary: JsonObject = {
            "submitted": True,
            "duplicate_rejected": duplicate_rejected,
            "coordinator_accepted": coordinator_accepted,
        }
        summary["receipt"] = receipt_summary
        summary["artifacts"] = artifacts
    return summary


def _heartbeat_or_raise(
    client: CoordinatorClient, runner_key: str, lease: Lease
) -> JsonObject:
    """Heartbeat, translating a 409 ``lease_lost`` into LeaseLost."""
    try:
        return client.heartbeat(runner_key, lease.job_id, lease.attempt)
    except CoordinatorError as exc:
        if exc.status_code == 409 and "lease_lost" in exc.detail:
            raise LeaseLost(exc.detail) from exc
        raise


def _outcome_status(
    result: ExecutionResult | None,
) -> tuple[str, int | None, str | None, dict | None]:
    """Map an execution result to (status, exit_code, error, denial)."""
    if result is None:
        return "inconclusive", None, None, None
    denied_effect = result.denied_effect
    status = "failed" if denied_effect is not None else result.status
    if status not in {"succeeded", "failed", "timed_out", "inconclusive"}:
        status = "inconclusive"
    return status, result.exit_code, None, denied_effect


def _publish(
    client: CoordinatorClient,
    signing_key,
    lease: Lease,
    *,
    runner_id: str,
    runner_key: str,
    status: str,
    started_at: str,
    finished_at: str,
    denied_effect: dict | None,
    result: ExecutionResult | None,
    runtime_digest: str,
    error: str | None = None,
) -> tuple[dict[str, str], bool, bool, JsonObject]:
    """Upload artifacts, build/sign/submit the receipt.

    Returns (artifacts, duplicate_rejected, coordinator_accepted).
    """
    artifacts: dict[str, str] = {}
    if result is not None:
        for name, data in result.output_files.items():
            response = client.upload_artifact(
                runner_key, lease.job_id, name, data
            )
            artifacts[name] = str(response.get("sha256", ""))
    exit_code: int | None = result.exit_code if result else None
    outcome = ExecutionOutcome(
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        exit_code=exit_code,
        error=error,
        effect_blocked=denied_effect is not None,
        effect_kind=(
            denied_effect.get("effect_kind") if denied_effect else None
        ),
        effect_detail=(
            denied_effect.get("effect_detail") if denied_effect else None
        ),
    )
    if result is None:
        vector = short_sha256({"status": status, "exit_code": None})
    else:
        vector = _assertion_vector_digest(result)
    receipt = build_receipt(
        ReceiptInput(
            job_id=lease.job_id,
            attempt=lease.attempt,
            runner_id=runner_id,
            runtime_digest=runtime_digest,
            sandbox_profile=lease.sandbox_profile,
            sandbox_profile_digest=lease.sandbox_profile_digest,
            contract_digest=lease.contract_digest,
            resource_id=lease.resource_id,
            resource_version_id=lease.resource_version_id,
            resource_digest=lease.resource_digest,
            input_digests=lease.input_digests,
            output_artifacts=artifacts,
            outcome=outcome,
            assertion_vector_digest=vector,
            redactions_applied=[],
            environment_fingerprint=_environment_fingerprint(),
            lease_holder=runner_id,
            idempotency_key=lease.idempotency_key,
        )
    )
    canonical, signature = sign_receipt(receipt, signing_key)
    body: JsonObject = {
        "client_receipt": json.loads(canonical.decode("utf-8")),
        "signature": signature.decode("ascii"),
        "signature_algorithm": SIGNATURE_ALGORITHM,
    }
    try:
        acceptance = client.submit_receipt(runner_key, lease.job_id, body)
    except CoordinatorError as exc:
        if exc.status_code == 409 and "duplicate" in exc.detail:
            # The coordinator already holds a receipt for this attempt
            # (an upload retry raced it). The terminal state is
            # unchanged; the duplicate was rejected.
            return artifacts, True, False, {"coordinator_accepted": False}
        raise
    return (
        artifacts,
        False,
        bool(acceptance.get("coordinator_accepted", True)),
        acceptance,
    )


def _environment_fingerprint() -> dict[str, str]:
    """Return non-sensitive runtime facts suitable for a receipt."""
    return {
        "implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
    }


def _submit_receipt_for_cancel(
    client: CoordinatorClient,
    runner_key: str,
    signing_key,
    lease: Lease,
    runner_id: str,
    runtime_digest: str,
    heartbeat: JsonObject,
) -> None:
    """Publish the cancelled terminal outcome after a cancel heartbeat."""
    del heartbeat
    _publish(
        client,
        signing_key,
        lease,
        runner_id=runner_id,
        runner_key=runner_key,
        status="cancelled",
        started_at=utc_now_iso(),
        finished_at=utc_now_iso(),
        denied_effect=None,
        result=None,
        runtime_digest=runtime_digest,
    )


def acceptance_ok(acceptance: JsonObject) -> bool:
    return bool(acceptance.get("coordinator_accepted", True))


def run_one_iteration(
    client: CoordinatorClient,
    backend: SandboxBackend,
    *,
    runner_id: str,
    runner_key: str,
    signing_key,
    capabilities: list[str],
    runtime_digest: str,
    state_store: StateStore | None = None,
) -> JsonObject:
    """Run exactly one lease/execute/attest pass and return a summary.

    Returns a JSON object with at least ``leased`` (bool) and, when a
    job ran, ``job_id`` and ``status``. Raises :class:`LeaseLost` when
    the coordinator took the lease away mid-run; every other terminal
    condition is reported, not raised.
    """
    lease_payload = client.lease(runner_key, capabilities)
    if lease_payload is None:
        return _record({"leased": False}, state_store)
    lease = Lease.from_json(lease_payload)

    beat = _heartbeat_or_raise(client, runner_key, lease)
    if beat.get("cancel_requested") is True:
        _submit_receipt_for_cancel(
            client,
            runner_key,
            signing_key,
            lease,
            runner_id,
            runtime_digest,
            beat,
        )
        return _record(_leased_summary(lease, "cancelled"), state_store)

    started_at = utc_now_iso()
    result: ExecutionResult | None = None
    error: str | None = None
    try:
        result = backend.execute(
            lease,
            _payload_for(lease),
            on_heartbeat=lambda: _heartbeat_or_raise(
                client, runner_key, lease
            ),
        )
    except (SandboxUnavailable, SandboxExecutionError) as exc:
        status = "failed"
        error = str(exc)
        result = None
    else:
        status = (
            "failed" if result.denied_effect is not None else result.status
        )
    finished_at = utc_now_iso()
    if status not in {"succeeded", "failed", "timed_out", "inconclusive"}:
        status = "inconclusive"

    _heartbeat_or_raise(client, runner_key, lease)

    denied_effect = result.denied_effect if result is not None else None
    artifacts, duplicate, accepted, acceptance = _publish(
        client,
        signing_key,
        lease,
        runner_id=runner_id,
        runner_key=runner_key,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        denied_effect=denied_effect,
        result=result,
        runtime_digest=runtime_digest,
        error=error,
    )
    summary = _leased_summary(
        lease,
        status,
        artifacts=artifacts,
        duplicate_rejected=duplicate,
        coordinator_accepted=accepted,
        coordinator_facts=acceptance,
    )
    return _record(summary, state_store)


def _record(summary: JsonObject, state_store: StateStore | None) -> JsonObject:
    if state_store:
        state_store.record(summary)
    return summary

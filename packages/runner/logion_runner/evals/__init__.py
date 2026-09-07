"""Map eval contracts onto the existing 15.15 job/lease envelope.

The adapter is a *mapping*, not a new runtime: an ``EvalContract``
resolves to a ``Lease``-shaped job, and an ``EvalResult`` is
normalized from the outcome the existing receipt already describes.
Nothing here invents a parallel execution path — the lease loop, the
sandbox profiles, and the receipt builder are reused as-is.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from logion_eval_contract import (
    EvalContract,
    EvalFixtureDigestMismatch,
    EvalRequirementUnsupported,
    EvalResult,
    JsonObject,
    ResultEnvironment,
    environment_digest_from,
)

#: Job type the coordinator leases for eval work. Reuses the 15.15
#: envelope; the coordinator carries no separate eval job type.
EVAL_JOB_TYPE = "eval"

#: Runtime requirements this adapter can satisfy. Anything else fails
#: before a lease is requested, which is what keeps
#: ``rejected_before_execution`` true.
SUPPORTED_REQUIREMENT_KINDS = ("sandbox_profile",)


class EvalAdapterError(Exception):
    """A contract cannot be mapped onto the job envelope."""


@dataclass(frozen=True)
class ResolvedEvalJob:
    """The Lease-shaped view of one validated contract."""

    job_type: str
    contract_digest: str
    sandbox_profile: JsonObject
    sandbox_profile_digest: str
    input_digests: dict[str, str]
    subject_digest: str
    idempotency_key: str


def subject_digest_for(subject_bytes: bytes) -> str:
    """The subject's content digest, bound at run time."""
    return hashlib.sha256(subject_bytes).hexdigest()


def resolve_eval_job(
    contract: EvalContract,
    subject_bytes: bytes,
    *,
    contract_dir: str | Path | None = None,
) -> ResolvedEvalJob:
    """Resolve every input before leasing or executing.

    A run that leases first and resolves later cannot satisfy
    ``rejected_before_execution: true`` — so unsupported requirements
    and subject mismatch raise here, before any lease exists. The
    parser already rejected unknown input names at validation time
    (``inputs`` is advisory naming; the resolved inputs are the
    declared fixtures plus each step's params).
    """
    for req in contract.runtime_requirements:
        if req.kind not in SUPPORTED_REQUIREMENT_KINDS:
            raise EvalRequirementUnsupported(
                f"runtime requirement kind {req.kind!r} is not supported"
                " by this runner"
            )
    subject_digest = subject_digest_for(subject_bytes)
    from logion_eval_contract import validate_subject

    validate_subject(contract, subject_digest)
    fixture_dir = Path(contract_dir) if contract_dir else None
    input_digests: dict[str, str] = {}
    for fixture in contract.fixtures:
        input_digests[f"fixture:{fixture.name}"] = fixture.digest
        if fixture_dir is not None:
            fixture_path = fixture_dir / fixture.name
            if not fixture_path.is_file():
                raise EvalFixtureDigestMismatch(
                    f"fixture {fixture.name!r} is not present at {fixture_dir}"
                )
            fixture_digest = hashlib.sha256(
                fixture_path.read_bytes()
            ).hexdigest()
            if fixture_digest != fixture.digest:
                raise EvalFixtureDigestMismatch(
                    f"fixture {fixture.name!r} bytes hash to"
                    f" {fixture_digest}, not the declared"
                    f" {fixture.digest}"
                )
    for step in contract.steps:
        # JCS-canonical JSON keeps the digest reproducible across
        # implementations, exactly like every other digest that flows
        # into the lease payload and the receipt.
        from logion_eval_contract import canonicalize

        input_digests[f"step:{step.id}"] = hashlib.sha256(
            canonicalize(step.params)
        ).hexdigest()
    input_digests["subject"] = subject_digest
    contract_digest = _contract_digest(contract)
    return ResolvedEvalJob(
        job_type=EVAL_JOB_TYPE,
        contract_digest=contract_digest,
        sandbox_profile={
            "runtime": "container",
            "image": _image_for(contract),
        },
        sandbox_profile_digest=_profile_digest(contract),
        input_digests=input_digests,
        subject_digest=subject_digest,
        idempotency_key=(f"eval:{contract_digest[:16]}:{subject_digest[:16]}"),
    )


def normalize_outcome(
    contract: EvalContract,
    subject_digest: str,
    environment: ResultEnvironment,
    assertion_vector: tuple,
    metrics: tuple,
    outcome: str,
    artifacts: JsonObject,
    resource_usage: JsonObject,
    limitations: str,
) -> EvalResult:
    """Build the normalized result from an execution's outcome."""
    from logion_eval_contract import EvalResult as _EvalResult

    return _EvalResult(
        contract_digest=_contract_digest(contract),
        subject_digest=subject_digest,
        environment=environment,
        assertion_vector=assertion_vector,
        metrics=metrics,
        outcome=outcome,
        artifacts=artifacts,
        resource_usage=resource_usage,
        limitations=limitations,
    )


def environment_for(
    harness_id: str,
    harness_version: str,
    model_id: str,
    model_version: str,
) -> tuple[ResultEnvironment, str]:
    """Return (environment, environment_digest) for the closed pair."""
    env = ResultEnvironment(
        harness_id=harness_id,
        harness_version=harness_version,
        model_id=model_id,
        model_version=model_version,
    )
    digest = environment_digest_from(
        harness_id, harness_version, model_id, model_version
    )
    return env, digest


def _image_for(contract: EvalContract) -> str:
    """The digest-pinned image the contract's requirements demand."""
    from logion_runner.sandbox.profiles import PROFILE_V0_NAME

    for req in contract.runtime_requirements:
        if req.kind == "sandbox_profile" and req.value != "pinned-image":
            raise EvalRequirementUnsupported(
                "sandbox_profile requirement must be 'pinned-image', got"
                f" {req.value!r}"
            )
    image_digest = _profile_digest(contract)
    return f"{PROFILE_V0_NAME}@sha256:{image_digest}"


def _profile_digest(contract: EvalContract) -> str:
    from logion_eval_contract import canonicalize

    profile = {
        "runtime": "container",
        "profile": "isolated-runner-v0",
        "contract_digest": _contract_digest(contract),
    }
    return hashlib.sha256(canonicalize(profile)).hexdigest()


def _contract_digest(contract: EvalContract) -> str:
    from logion_eval_contract import contract_digest as _digest

    return _digest(contract)

"""Build and sign the execution receipt a runner publishes per job.

A receipt is the runner's attestation of one attempt: what ran, with
which inputs, producing which outputs, under which sandbox profile, and
with what outcome. The coordinator verifies the signature over the
JCS-canonicalized receipt bytes before accepting it, so the builder and
every verifier must serialize identically — that is what
:mod:`logion_runner._jcs` guarantees.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from logion_runner._jcs import canonicalize
from logion_runner._json import JsonObject

RECEIPT_SCHEMA_VERSION = "1"
SIGNATURE_ALGORITHM = "Ed25519"

#: Keys redacted from receipts before publication. Values for these
#: fields never reach the coordinator; only the fact that a redaction
#: was applied is recorded.
REDACTED_KEYS = frozenset({
    "token",
    "secret",
    "password",
    "api_key",
    "authorization",
    "credential",
    "private_key",
})


@dataclass(frozen=True)
class ExecutionOutcome:
    """What happened during one attempt inside the sandbox."""

    status: str
    started_at: str
    finished_at: str
    exit_code: int | None = None
    error: str | None = None
    effect_blocked: bool = False
    effect_kind: str | None = None
    effect_detail: str | None = None


@dataclass(frozen=True)
class ReceiptInput:
    """Everything the builder needs to attest one attempt."""

    job_id: str
    attempt: int
    runner_id: str
    runtime_digest: str
    sandbox_profile: str
    sandbox_profile_digest: str
    contract_digest: str
    resource_id: str
    resource_version_id: str
    resource_digest: str
    input_digests: dict[str, str]
    output_artifacts: dict[str, str]
    outcome: ExecutionOutcome
    assertion_vector_digest: str
    redactions_applied: list[str]
    environment_fingerprint: dict[str, str]
    lease_holder: str | None = None
    idempotency_key: str | None = None


def utc_now_iso() -> str:
    """Current UTC time as a second-precision ISO-8601 Z timestamp."""
    return (
        datetime
        .now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def redact(value: JsonObject) -> tuple[JsonObject, list[str]]:
    """Return (redacted copy, redacted key paths).

    Any key whose lowercase name contains a redacted marker has its
    value replaced with ``"[REDACTED]"`` and the path recorded. The
    receipt then carries the *fact* of the redaction, never the value.
    """
    redactions: list[str] = []

    def walk(node: JsonObject, prefix: str) -> JsonObject:
        out: JsonObject = {}
        for key, item in node.items():
            path = f"{prefix}.{key}" if prefix else key
            lowered = key.lower()
            if (
                any(marker in lowered for marker in REDACTED_KEYS)
                and isinstance(item, str)
                and item
            ):
                redactions.append(path)
                out[key] = "[REDACTED]"
                continue
            if isinstance(item, dict):
                out[key] = walk(item, path)
            else:
                out[key] = item
        return out

    return walk(value, ""), sorted(set(redactions))


def build_receipt(data: ReceiptInput) -> JsonObject:
    """Build the receipt object (unsigned, uncanonicalized)."""
    outcome: JsonObject = {
        "status": data.outcome.status,
        "started_at": data.outcome.started_at,
        "finished_at": data.outcome.finished_at,
        "exit_code": data.outcome.exit_code,
    }
    if data.outcome.error:
        outcome["error"] = data.outcome.error
    if data.outcome.effect_blocked:
        outcome["effect_blocked"] = True
        outcome["effect_kind"] = data.outcome.effect_kind
        if data.outcome.effect_detail:
            outcome["effect_detail"] = data.outcome.effect_detail
    redacted_environment, env_redactions = redact(
        dict(data.environment_fingerprint)
    )
    receipt: JsonObject = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "job_id": data.job_id,
        "attempt": data.attempt,
        "runner_id": data.runner_id,
        "runtime_digest": data.runtime_digest,
        "sandbox_profile": data.sandbox_profile,
        "sandbox_profile_digest": data.sandbox_profile_digest,
        "contract_digest": data.contract_digest,
        "resource": {
            "id": data.resource_id,
            "version_id": data.resource_version_id,
            "digest": data.resource_digest,
        },
        "input_digests": data.input_digests,
        "output_artifacts": data.output_artifacts,
        "assertion_vector_digest": data.assertion_vector_digest,
        "outcome": outcome,
        "redactions_applied": data.redactions_applied + env_redactions,
        "environment_fingerprint": redacted_environment,
    }
    if data.lease_holder:
        receipt["lease_holder"] = data.lease_holder
    if data.idempotency_key:
        receipt["idempotency_key"] = data.idempotency_key
    return receipt


def sign_receipt(
    receipt: JsonObject, signing_key: Ed25519PrivateKey
) -> tuple[bytes, bytes]:
    """Return (canonical_bytes, base64 signature over them).

    Signing happens over exactly the bytes the coordinator will
    re-canonicalize: the JCS form of the receipt as built. Any later
    mutation of the receipt (including key reordering) changes the
    digest and breaks the signature.
    """
    canonical = canonicalize(receipt)
    signature = signing_key.sign(canonical)
    return canonical, base64.b64encode(signature)


def timestamp_pair() -> tuple[str, str]:
    """Convenience: (started_at, finished_at) for an instant."""
    now = utc_now_iso()
    return now, now


def monotonic_deadline(wall_seconds: int) -> float:
    """Absolute monotonic deadline for a wall-clock limit."""
    return time.monotonic() + wall_seconds


def serialize_private_key(key: Ed25519PrivateKey) -> str:
    """PEM-encode an Ed25519 private key (unencrypted PKCS#8)."""
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("ascii")

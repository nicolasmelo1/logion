"""Typed views over the coordinator's lease envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from logion_runner._json import JsonObject, opt_str, require_int

SandboxProfile = dict[str, object]


@dataclass(frozen=True)
class JobLimits:
    """Wall/memory/output/log limits the coordinator grants a job."""

    wall_seconds: int
    memory_bytes: int
    output_bytes: int
    log_bytes: int

    @classmethod
    def from_json(cls, payload: JsonObject) -> JobLimits:
        return cls(
            wall_seconds=require_int(payload, "wall_seconds"),
            memory_bytes=require_int(payload, "memory_bytes"),
            output_bytes=require_int(payload, "output_bytes"),
            log_bytes=require_int(payload, "log_bytes"),
        )


@dataclass(frozen=True)
class ArtifactGrant:
    """One output artifact the coordinator expects, with its digest."""

    name: str
    sha256: str

    @classmethod
    def from_json(cls, payload: JsonObject) -> ArtifactGrant:
        return cls(
            name=opt_str(payload, "name") or "",
            sha256=opt_str(payload, "sha256") or "",
        )


@dataclass(frozen=True)
class Lease:
    """A job the runner claimed, or the reason it got nothing."""

    job_id: str
    attempt: int
    job_type: str
    contract_digest: str
    sandbox_profile: SandboxProfile
    sandbox_profile_digest: str
    resource_id: str
    resource_version_id: str
    resource_digest: str
    required_capabilities: list[str]
    input_digests: dict[str, str]
    limits: JobLimits
    artifacts: list[ArtifactGrant]
    idempotency_key: str
    lease_expires_at: str
    effect: str | None = None

    @classmethod
    def from_json(cls, payload: JsonObject) -> Lease:
        artifacts_payload = payload.get("artifacts")
        artifacts = (
            [
                ArtifactGrant.from_json(item)
                for item in artifacts_payload
                if isinstance(item, dict)
            ]
            if isinstance(artifacts_payload, list)
            else []
        )
        limits_payload = payload.get("limits")
        return cls(
            job_id=opt_str(payload, "job_id") or "",
            attempt=require_int(payload, "attempt"),
            job_type=opt_str(payload, "job_type") or "",
            contract_digest=opt_str(payload, "contract_digest") or "",
            sandbox_profile=_profile_map(payload.get("sandbox_profile")),
            sandbox_profile_digest=(
                opt_str(payload, "sandbox_profile_digest") or ""
            ),
            resource_id=opt_str(payload, "resource_id") or "",
            resource_version_id=opt_str(payload, "resource_version_id") or "",
            resource_digest=opt_str(payload, "resource_digest") or "",
            required_capabilities=[
                item
                for item in _str_list(payload.get("required_capabilities"))
                if item
            ],
            input_digests=_str_map(payload.get("input_digests")),
            # The coordinator does not carry an `effect` field; the
            # adversarial fixture declares its effect via input_digests so
            # the whole envelope stays inside the public contract.
            effect=opt_str(payload, "effect")
            or _str_map(payload.get("input_digests")).get("effect")
            or None,
            limits=JobLimits.from_json(
                limits_payload if isinstance(limits_payload, dict) else {}
            ),
            artifacts=artifacts,
            idempotency_key=opt_str(payload, "idempotency_key") or "",
            lease_expires_at=opt_str(payload, "lease_expires_at") or "",
        )


def _str_list(value: object) -> list[str]:
    """Narrow a JSON value to a list of strings (skipping others)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _str_map(value: object) -> dict[str, str]:
    """Narrow a JSON value to a string-to-string mapping."""
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, str)
    }


def _profile_map(value: object) -> SandboxProfile:
    if not isinstance(value, dict):
        return {}
    return cast(
        SandboxProfile,
        {str(key): item for key, item in value.items()},
    )


TERMINAL_STATUSES = (
    "succeeded",
    "failed",
    "timed_out",
    "cancelled",
    "inconclusive",
)


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES

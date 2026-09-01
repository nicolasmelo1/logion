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
        limits_payload = payload.get("limits")
        return cls(
            job_id=_text(payload, "job_id"),
            attempt=require_int(payload, "attempt"),
            job_type=_text(payload, "job_type"),
            contract_digest=_text(payload, "contract_digest"),
            sandbox_profile=_profile_map(payload.get("sandbox_profile")),
            sandbox_profile_digest=_text(payload, "sandbox_profile_digest"),
            resource_id=_text(payload, "resource_id"),
            resource_version_id=_text(payload, "resource_version_id"),
            resource_digest=_text(payload, "resource_digest"),
            required_capabilities=_capabilities(payload),
            input_digests=_str_map(payload.get("input_digests")),
            effect=_effect(payload),
            limits=JobLimits.from_json(
                limits_payload if isinstance(limits_payload, dict) else {}
            ),
            artifacts=_artifacts(payload),
            idempotency_key=_text(payload, "idempotency_key"),
            lease_expires_at=_text(payload, "lease_expires_at"),
        )


def _text(payload: JsonObject, key: str) -> str:
    """A string field, or ``""`` when absent or the wrong type."""
    return opt_str(payload, key) or ""


def _artifacts(payload: JsonObject) -> list[ArtifactGrant]:
    raw = payload.get("artifacts")
    if not isinstance(raw, list):
        return []
    return [
        ArtifactGrant.from_json(item) for item in raw if isinstance(item, dict)
    ]


def _capabilities(payload: JsonObject) -> list[str]:
    return [
        item
        for item in _str_list(payload.get("required_capabilities"))
        if item
    ]


def _effect(payload: JsonObject) -> str | None:
    """The adversarial fixture's declared effect, if the job names one.

    The coordinator carries no ``effect`` field, so the fixture declares
    it through ``input_digests`` and the whole envelope stays inside the
    public contract.
    """
    return (
        opt_str(payload, "effect")
        or _str_map(payload.get("input_digests")).get("effect")
        or None
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

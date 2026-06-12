"""Policy loading and evaluation."""

from __future__ import annotations

import hashlib
from importlib import resources

import yaml

from logion_scanners.models import (
    PolicyDecision,
    ScannerFinding,
    ScanPolicy,
)


def load_policy(policy_id: str) -> ScanPolicy:
    """Load a named policy from the bundled policies directory."""
    _validate_policy_id(policy_id)
    raw = _read_policy_yaml(policy_id)
    data = yaml.safe_load(raw)
    return ScanPolicy(
        policy_id=data["policy_id"],
        policy_version=data["policy_version"],
        required_scanners=tuple(data["required_scanners"]),
        enabled_agent_checks=tuple(data["enabled_agent_checks"]),
        blocking_severities={
            k: tuple(v) for k, v in data["blocking_severities"].items()
        },
        max_bundle_size_mb=data["max_bundle_size_mb"],
        max_file_count=data["max_file_count"],
        max_file_size_mb=data["max_file_size_mb"],
        scanner_timeout_seconds=data["scanner_timeout_seconds"],
        block_on_scanner_unavailable=data["block_on_scanner_unavailable"],
    )


def policy_hash(policy_id: str) -> str:
    """Return the SHA-256 hex digest of the raw policy YAML bytes."""
    _validate_policy_id(policy_id)
    raw = _read_policy_yaml(policy_id)
    return hashlib.sha256(raw).hexdigest()


def evaluate(
    policy: ScanPolicy,
    results: list,  # list[ScannerResult]
) -> PolicyDecision:
    """Evaluate scanner results against a policy.

    A result blocks publication when:
    1. A finding's severity is in blocking_severities[its layer], OR
    2. A required scanner is missing/errored and
       block_on_scanner_unavailable is true.
    """
    blocking: list[ScannerFinding] = []
    reasons: list[str] = []

    result_layers = {r.layer for r in results}

    # Check for missing required scanners.
    for scanner_id in policy.required_scanners:
        if (
            scanner_id not in result_layers
            and policy.block_on_scanner_unavailable
        ):
            reasons.append(
                f"Required scanner {scanner_id!r} did not produce a result"
            )

    # Check each result.
    for result in results:
        blocking_sevs = policy.blocking_severities.get(result.layer, ())
        for finding in result.findings:
            if finding.severity in blocking_sevs:
                blocking.append(finding)
                reasons.append(
                    f"{finding.rule_id}: {finding.description} "
                    f"({finding.severity})"
                )

        # Scanner errored with no findings — synthesize a block.
        if (
            result.error
            and not result.findings
            and result.layer in policy.required_scanners
            and policy.block_on_scanner_unavailable
        ):
            reasons.append(f"Scanner {result.layer!r} errored: {result.error}")

    allowed = len(reasons) == 0
    return PolicyDecision(
        allowed=allowed,
        blocking_findings=tuple(blocking),
        reasons=tuple(reasons),
    )


def _validate_policy_id(policy_id: str) -> None:
    """Only allow known policy IDs to prevent path traversal."""
    if policy_id not in {"publication-v1"}:
        raise ValueError(
            f"Unknown policy: {policy_id!r}. Available: publication-v1"
        )


def _read_policy_yaml(policy_id: str) -> bytes:
    """Read raw YAML bytes from the policies package."""
    ref = resources.files("logion_scanners.policies").joinpath(
        f"{policy_id}.yaml"
    )
    return ref.read_bytes()

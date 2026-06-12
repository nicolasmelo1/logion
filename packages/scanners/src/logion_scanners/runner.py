"""Scan runner — orchestrate adapters and produce a ScanReport."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from logion_scanners.adapters.base import BaseScanner
from logion_scanners.models import (
    ScannerResult,
    ScanPolicy,
    ScanReport,
)
from logion_scanners.policy import evaluate


def bundle_hash(bundle: Path) -> str:
    """Compute a deterministic SHA-256 hash of the bundle contents.

    Sort by relative path to make the hash order-independent.
    """
    pairs: list[tuple[str, bytes]] = []
    for p in sorted(bundle.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(bundle))
        try:
            data = p.read_bytes()
        except OSError:
            continue
        pairs.append((rel, data))

    h = hashlib.sha256()
    for rel, data in pairs:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return h.hexdigest()


def run_scan(
    *,
    bundle: Path,
    policy: ScanPolicy,
    adapters: Sequence[BaseScanner],
) -> ScanReport:
    """Run all adapters against a bundle and produce a ScanReport.

    If an adapter raises an exception, it is captured as an
    errored ScannerResult rather than aborting the entire run.
    """
    bhash = bundle_hash(bundle)
    phash = _policy_hash_from_policy(policy)

    results: list[ScannerResult] = []
    execution_error: str | None = None

    for adapter in adapters:
        try:
            result = adapter.scan(bundle)
            results.append(result)
        except Exception as exc:
            results.append(
                ScannerResult(
                    layer=adapter.layer,
                    passed=False,
                    error=str(exc),
                )
            )
            execution_error = f"{adapter.layer} raised: {exc}"

    decision = evaluate(policy, results)

    return ScanReport(
        schema_version=1,
        bundle_hash=bhash,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_hash=phash,
        results=results,
        execution_error=execution_error,
        decision=decision,
    )


def _policy_hash_from_policy(policy: ScanPolicy) -> str:
    """Compute the policy hash from a loaded ScanPolicy object.

    This re-reads the raw YAML to produce a hash consistent with
    policy_hash(), rather than hashing the in-memory representation.
    """
    from logion_scanners.policy import policy_hash

    return policy_hash(policy.policy_id)

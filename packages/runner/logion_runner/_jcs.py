"""JCS-style canonical JSON (RFC 8785 subset) — single implementation.

The canonicalization the coordinator, every receipt verifier, and the
eval contract library agree on lives in the published
``logion-eval-contract`` package (``logion_eval_contract.canonical``).
This module re-exports it so the runner keeps its import paths: a
second implementation here is exactly the silent divergence that
``api.canonical_digest_agrees`` exists to catch — the receipt bytes and
the contract digest must come from one algorithm, not two.
"""

from __future__ import annotations

from logion_eval_contract.canonical import (
    canonicalize,
    canonicalize_text,
    is_round_trip_stable,
    short_sha256,
)

__all__ = [
    "canonicalize",
    "canonicalize_text",
    "is_round_trip_stable",
    "short_sha256",
]

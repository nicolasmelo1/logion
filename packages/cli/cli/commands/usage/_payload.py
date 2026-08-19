# SPDX-License-Identifier: MIT
"""Helpers for extracting observation fields from hook payloads."""

from __future__ import annotations

from cli._json import JsonObject, opt_str
from cli.usage.observations import DURATION_BUCKETS, OUTCOME_VALUES


def payload_outcome(payload: JsonObject) -> str:
    """Narrow the wire value to a known outcome, defaulting to unknown."""
    value = opt_str(payload, "outcome")
    if value and value in OUTCOME_VALUES:
        return value
    return "unknown"


def payload_duration_bucket(payload: JsonObject) -> str | None:
    """Extract a validated duration bucket, or None if absent/invalid."""
    value = opt_str(payload, "duration_bucket")
    if value and value in DURATION_BUCKETS:
        return value
    return None

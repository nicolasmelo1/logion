# SPDX-License-Identifier: MIT
"""Confidence calibration helpers for local recall.

Maps raw similarity scores to calibrated confidence values and
categorical bands used by the companion's decision policy.
"""

from __future__ import annotations

import datetime as _dt


def _parse_last_success_at(value: str | None) -> _dt.datetime | None:
    if not value:
        return None

    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = _dt.datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_dt.UTC)
    return parsed


def calibrate_installed_confidence(query_similarity: float) -> float:
    """Installed capabilities have no prior beyond presence.

    The query similarity is the entire signal.
    """
    return query_similarity


def calibrate_workflow_confidence(
    query_similarity: float,
    success_count: int = 0,
    last_success_at: str | None = None,
) -> float:
    """Combine query similarity with persisted workflow prior and recency.

    ``final = clamp(
        0, 1,
        0.6 * query_similarity
        + 0.3 * persisted_prior
        + 0.1 * recency_boost,
    )``
    """
    persisted_prior = min(success_count / 10, 1.0)

    recency_boost = 0.0
    last = _parse_last_success_at(last_success_at)
    if last is not None:
        now = _dt.datetime.now(_dt.UTC)
        if last > now:
            last = now
        days_ago = (now - last).days
        if days_ago <= 30:
            recency_boost = 1.0
        elif days_ago <= 365:
            recency_boost = 1.0 - (days_ago - 30) / (365 - 30)
        # beyond 365 days → 0.0

    final = (
        0.6 * query_similarity + 0.3 * persisted_prior + 0.1 * recency_boost
    )
    return max(0.0, min(1.0, final))


def band_for(confidence: float) -> str:
    """Return the categorical band for a confidence value.

    - HIGH   : confidence >= 0.80
    - MEDIUM : 0.50 <= confidence < 0.80
    - LOW    : 0.20 <= confidence < 0.50
    - NONE   : confidence < 0.20
    """
    if confidence >= 0.80:
        return "HIGH"
    if confidence >= 0.50:
        return "MEDIUM"
    if confidence >= 0.20:
        return "LOW"
    return "NONE"

# SPDX-License-Identifier: MIT
"""Deterministic ranker for the local recall index.

Pure function: given a query and a list of compact recall entries,
returns a sorted, top-k list with per-entry similarity in [0, 1].

Uses ``rapidfuzz.fuzz.partial_token_set_ratio`` when available, falls
back to ``difflib.SequenceMatcher.ratio()`` otherwise. The fallback
must produce stable (but possibly lower-quality) rankings.
"""

from __future__ import annotations

import difflib
from typing import Any

try:
    from rapidfuzz import fuzz as _rapidfuzz_fuzz

    _rf_fuzz: Any | None = _rapidfuzz_fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    _rf_fuzz = None
    _HAS_RAPIDFUZZ = False


_MINIMUM_SIMILARITY = 0.10


def _compute_similarity(query: str, composed: str) -> float:
    """Return similarity in [0, 1] between *query* and *composed* string."""
    if _HAS_RAPIDFUZZ and _rf_fuzz is not None:
        return _rf_fuzz.partial_token_set_ratio(query, composed) / 100.0
    return difflib.SequenceMatcher(None, query, composed).ratio()


def _compose_entry_text(entry: dict[str, Any]) -> str:
    """Build a single lowercase string from entry fields for matching."""
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    tokens = entry.get("tokens") or []
    return f"{title} {summary} {' '.join(tokens)}".lower()


def rank(
    query: str,
    entries: list[dict[str, Any]],
    limit: int = 5,
) -> list[tuple[float, dict[str, Any]]]:
    """Return up to *limit* ``(similarity, entry)`` tuples, sorted desc.

    Ranking is deterministic: entries with equal similarity are ordered
    by ``id`` ascending for stability.
    """
    if not entries or not query:
        return []

    q = query.strip().lower()
    if not q:
        return []

    scored: list[tuple[float, str, dict[str, Any]]] = []
    for entry in entries:
        composed = _compose_entry_text(entry)
        similarity = _compute_similarity(q, composed)
        if similarity < _MINIMUM_SIMILARITY:
            continue
        entry_id = entry.get("id", "")
        scored.append((similarity, entry_id, entry))

    # Sort by similarity desc, then id asc for tie-breaking stability
    scored.sort(key=lambda t: (-t[0], t[1]))

    return [(s, e) for s, _eid, e in scored[:limit]]

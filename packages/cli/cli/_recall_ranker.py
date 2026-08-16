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
import re
from types import ModuleType

from cli._json import JsonObject, opt_str, strings

try:
    from rapidfuzz import fuzz as _rapidfuzz_fuzz

    _rf_fuzz: ModuleType | None = _rapidfuzz_fuzz
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


def _token_similarity(query: str, tokens: list[str]) -> float:
    """Return token-set overlap similarity in [0, 1]."""
    q_tokens = {
        token for token in re.split(r"[^A-Za-z0-9]+", query.lower()) if token
    }
    e_tokens: set[str] = set()
    for token in tokens:
        e_tokens.update(
            piece
            for piece in re.split(r"[^A-Za-z0-9]+", str(token).lower())
            if piece
        )
    if not q_tokens or not e_tokens:
        return 0.0
    return len(q_tokens & e_tokens) / len(q_tokens | e_tokens)


def _compose_entry_text(entry: JsonObject) -> str:
    """Build a single lowercase string from entry fields for matching."""
    title = opt_str(entry, "title", "")
    summary = opt_str(entry, "summary", "")
    tokens = strings(entry, "tokens")
    return f"{title} {summary} {' '.join(tokens)}".lower()


def rank(
    query: str,
    entries: list[JsonObject],
    limit: int = 5,
) -> list[tuple[float, JsonObject]]:
    """Return up to *limit* ``(similarity, entry)`` tuples, sorted desc.

    Ranking is deterministic: entries with equal similarity are ordered
    by ``id`` ascending for stability.
    """
    if not entries or not query:
        return []

    q = query.strip().lower()
    if not q:
        return []

    scored: list[tuple[float, str, JsonObject]] = []
    for entry in entries:
        composed = _compose_entry_text(entry)
        similarity = max(
            _compute_similarity(q, composed),
            _token_similarity(q, strings(entry, "tokens")),
        )
        if similarity < _MINIMUM_SIMILARITY:
            continue
        entry_id = opt_str(entry, "id", "")
        scored.append((similarity, entry_id, entry))

    # Sort by similarity desc, then id asc for tie-breaking stability
    scored.sort(key=lambda t: (-t[0], t[1]))

    return [(s, e) for s, _eid, e in scored[:limit]]

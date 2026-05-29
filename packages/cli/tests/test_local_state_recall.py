"""Unit tests for the recall fuzzy ranker and confidence calibration."""

from __future__ import annotations

import datetime as _dt
from unittest import mock

import pytest

from cli._recall_calibration import (
    band_for,
    calibrate_installed_confidence,
    calibrate_workflow_confidence,
)
from cli._recall_ranker import rank

# ---------------------------------------------------------------------------
# §1.4  Band / calibration tests
# ---------------------------------------------------------------------------


class TestBandFor:
    def test_high_threshold(self) -> None:
        assert band_for(0.80) == "HIGH"
        assert band_for(0.95) == "HIGH"
        assert band_for(1.0) == "HIGH"

    def test_medium_threshold(self) -> None:
        assert band_for(0.50) == "MEDIUM"
        assert band_for(0.79) == "MEDIUM"
        assert band_for(0.65) == "MEDIUM"

    def test_low_threshold(self) -> None:
        assert band_for(0.20) == "LOW"
        assert band_for(0.49) == "LOW"
        assert band_for(0.35) == "LOW"

    def test_none_below_zero_point_two(self) -> None:
        assert band_for(0.19) == "NONE"
        assert band_for(0.0) == "NONE"
        assert band_for(0.001) == "NONE"


class TestCalibrateInstalledConfidence:
    def test_returns_query_similarity_directly(self) -> None:
        assert calibrate_installed_confidence(0.75) == 0.75

    def test_zero(self) -> None:
        assert calibrate_installed_confidence(0.0) == 0.0


class TestCalibrateWorkflowConfidence:
    def test_saturates_at_ten_successes(self) -> None:
        result = calibrate_workflow_confidence(
            query_similarity=0.5,
            success_count=10,
            last_success_at=None,
        )
        expected = 0.6 * 0.5 + 0.3 * 1.0 + 0.1 * 0.0
        assert abs(result - expected) < 0.001

        # More than 10 should not increase further
        result2 = calibrate_workflow_confidence(
            query_similarity=0.5,
            success_count=50,
            last_success_at=None,
        )
        assert abs(result2 - expected) < 0.001

    def test_recency_decay_within_thirty_days(self) -> None:
        recent = (
            _dt.datetime.now(_dt.UTC) - _dt.timedelta(days=5)
        ).isoformat()
        result = calibrate_workflow_confidence(
            query_similarity=0.5,
            success_count=0,
            last_success_at=recent,
        )
        assert result == pytest.approx(0.6 * 0.5 + 0.3 * 0.0 + 0.1 * 1.0)

    def test_recency_floor_at_one_year(self) -> None:
        old = (_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=400)).isoformat()
        result = calibrate_workflow_confidence(
            query_similarity=0.5,
            success_count=0,
            last_success_at=old,
        )
        assert result == pytest.approx(0.6 * 0.5)

    def test_combines_components_with_documented_weights(self) -> None:
        recent = (
            _dt.datetime.now(_dt.UTC) - _dt.timedelta(days=10)
        ).isoformat()
        result = calibrate_workflow_confidence(
            query_similarity=0.7,
            success_count=5,
            last_success_at=recent,
        )
        expected = 0.6 * 0.7 + 0.3 * 0.5 + 0.1 * 1.0
        assert abs(result - expected) < 0.001

    def test_clamps_to_one(self) -> None:
        recent = (
            _dt.datetime.now(_dt.UTC) - _dt.timedelta(days=0)
        ).isoformat()
        result = calibrate_workflow_confidence(
            query_similarity=1.0,
            success_count=100,
            last_success_at=recent,
        )
        assert result <= 1.0

    def test_invalid_last_success_at_treated_as_zero(self) -> None:
        result = calibrate_workflow_confidence(
            query_similarity=0.5,
            success_count=0,
            last_success_at="not-a-date",
        )
        assert result == pytest.approx(0.6 * 0.5)


# ---------------------------------------------------------------------------
# §2.4  Ranker tests
# ---------------------------------------------------------------------------


class TestRank:
    @pytest.fixture
    def sample_entries(self) -> list[dict]:
        return [
            {
                "id": "workflow.verify-agent-companion",
                "type": "workflow",
                "title": "Verify agent companion package",
                "summary": "Run lint, typecheck, tests, packaging checks.",
                "tokens": [],
            },
            {
                "id": "workflow.python-lint",
                "type": "workflow",
                "title": "Lint Python code",
                "summary": "Run ruff check on source files.",
                "tokens": [],
            },
            {
                "id": "workflow.deploy-prod",
                "type": "workflow",
                "title": "Deploy to production",
                "summary": "Push image and rollout.",
                "tokens": [],
            },
        ]

    def test_returns_at_most_limit(self, sample_entries: list[dict]) -> None:
        result = rank("verify agent", sample_entries, limit=1)
        assert len(result) <= 1

    def test_sorted_by_similarity_desc_then_id_asc(
        self, sample_entries: list[dict]
    ) -> None:
        result = rank("lint", sample_entries, limit=10)
        sims = [s for s, _ in result]
        assert sims == sorted(sims, reverse=True)

    def test_drops_below_minimum_prefilter(
        self, sample_entries: list[dict]
    ) -> None:
        totally_unrelated = rank("zzzzzzzzz", sample_entries, limit=10)
        # All entries should score very low; likely all dropped
        for sim, _ in totally_unrelated:
            assert sim >= 0.10

    def test_handles_empty_entries_returns_empty(self) -> None:
        assert rank("anything", [], limit=5) == []

    def test_handles_empty_query_returns_empty(
        self, sample_entries: list[dict]
    ) -> None:
        assert rank("", sample_entries, limit=5) == []
        assert rank("   ", sample_entries, limit=5) == []

    def test_deterministic_for_identical_input(
        self, sample_entries: list[dict]
    ) -> None:
        q = "verify agent companion"
        r1 = rank(q, sample_entries, limit=5)
        r2 = rank(q, sample_entries, limit=5)
        assert r1 == r2

    def test_partial_token_set_matches_reordered_query_tokens(
        self, sample_entries: list[dict]
    ) -> None:
        # "companion agent verify" is a token reordering of the title
        result = rank("companion agent verify", sample_entries, limit=3)
        ids = [e.get("id", "") for _, e in result]
        assert "workflow.verify-agent-companion" in ids

    def test_fallback_to_difflib_when_rapidfuzz_missing(
        self, sample_entries: list[dict]
    ) -> None:
        import cli._recall_ranker as mod

        orig = mod._HAS_RAPIDFUZZ
        try:
            mod._HAS_RAPIDFUZZ = False
            result = rank("verify agent", sample_entries, limit=3)
            assert len(result) >= 1
        finally:
            mod._HAS_RAPIDFUZZ = orig


class TestRapidfuzzAndDifflibSameBand:
    def test_produce_same_band_on_strong_match(self) -> None:
        import cli._recall_ranker as mod

        entries = [
            {
                "id": "workflow.verify-agent-companion",
                "type": "workflow",
                "title": "Verify agent companion package",
                "summary": "Run lint, typecheck, tests, packaging checks.",
                "tokens": [],
            },
        ]

        orig = mod._HAS_RAPIDFUZZ
        strong_query = (
            "verify agent companion package "
            "run lint, typecheck, tests, packaging checks."
        )
        try:
            mod._HAS_RAPIDFUZZ = True
            result_rf = rank(strong_query, entries, limit=5)
            band_rf = band_for(result_rf[0][0]) if result_rf else "NONE"

            mod._HAS_RAPIDFUZZ = False
            result_dl = rank(strong_query, entries, limit=5)
            band_dl = band_for(result_dl[0][0]) if result_dl else "NONE"
        finally:
            mod._HAS_RAPIDFUZZ = orig

        assert band_rf == "HIGH"
        assert band_dl == "HIGH"


# ---------------------------------------------------------------------------
# §7.1  Integration tests for search_recall
# ---------------------------------------------------------------------------


class TestSearchRecallIntegration:
    def test_recomputes_confidence_not_persisted_value(self) -> None:
        """search_recall must override persisted confidence with calibrated."""
        from cli._local_state import search_recall

        home = mock.MagicMock()
        entries = [
            {
                "id": "workflow.test",
                "type": "workflow",
                "title": "Test workflow",
                "summary": "Run integration tests.",
                "confidence": 0.91,  # persisted prior
                "source": "workflow_history",
                "commands": ["pytest tests/"],
                "success_count": 3,
                "last_success_at": "2020-01-01T00:00:00Z",
                "danger_flags": [],
                "tokens": [],
            },
        ]
        with mock.patch("cli._local_state.read_recall", return_value=entries):
            results = search_recall("test workflow", home=home, limit=5)
        assert results
        expected = calibrate_workflow_confidence(
            results[0]["query_similarity"],
            entries[0]["success_count"],
            entries[0]["last_success_at"],
        )
        assert results[0]["confidence"] != 0.91
        assert results[0]["confidence"] == pytest.approx(round(expected, 4))
        assert "band" in results[0]
        assert "query_similarity" in results[0]

    def test_build_recall_entries_preserve_id_and_command_searchability(
        self,
    ) -> None:
        from cli._local_state import build_recall_entries, search_recall

        entries = build_recall_entries(
            installed=[],
            workflows=[
                {
                    "id": "workflow.verify-agent-companion",
                    "title": "Utility workflow",
                    "commands": ["make -C packages/agent-companion verify"],
                    "success_count": 4,
                    "last_success_at": "2026-05-20T00:00:00Z",
                    "confidence": 0.5,
                }
            ],
        )
        with mock.patch("cli._local_state.read_recall", return_value=entries):
            by_id = search_recall(
                "workflow.verify-agent-companion",
                home=mock.MagicMock(),
                limit=5,
            )
            by_command = search_recall(
                "agent-companion verify",
                home=mock.MagicMock(),
                limit=5,
            )
        assert by_id
        assert by_command
        assert by_id[0]["id"] == "workflow.verify-agent-companion"
        assert by_command[0]["id"] == "workflow.verify-agent-companion"

    def test_attaches_band_to_each_match(self) -> None:
        from cli._local_state import search_recall

        entries = [
            {
                "id": "installed.x",
                "type": "installed_capability",
                "title": "X tool",
                "summary": "Does X things",
                "confidence": 0.91,
                "danger_flags": [],
                "tokens": [],
            },
        ]
        with mock.patch("cli._local_state.read_recall", return_value=entries):
            results = search_recall("x tool", home=mock.MagicMock(), limit=5)
        for r in results:
            assert "band" in r
            assert r["band"] in {"HIGH", "MEDIUM", "LOW"}

    def test_filters_band_none_from_results(self) -> None:
        from cli._local_state import search_recall

        # An entry that will score very low → NONE band → filtered out
        entries = [
            {
                "id": "workflow.unrelated",
                "type": "workflow",
                "title": "Deploy to production",
                "summary": "Push image and rollout.",
                "confidence": 0.5,
                "success_count": 0,
                "last_success_at": "2020-01-01T00:00:00Z",
                "danger_flags": [],
                "commands": [],
                "tokens": [],
            },
        ]
        with mock.patch("cli._local_state.read_recall", return_value=entries):
            results = search_recall(
                "zzzzzzzzz", home=mock.MagicMock(), limit=5
            )
        for r in results:
            assert r.get("band") != "NONE"

    def test_idempotent_across_calls(self) -> None:
        from cli._local_state import search_recall

        entries = [
            {
                "id": "installed.x",
                "type": "installed_capability",
                "title": "X tool",
                "summary": "Does X things",
                "confidence": 0.91,
                "danger_flags": [],
                "tokens": [],
            },
        ]
        home = mock.MagicMock()
        with mock.patch("cli._local_state.read_recall", return_value=entries):
            r1 = search_recall("x tool", home=home, limit=5)
            r2 = search_recall("x tool", home=home, limit=5)
        assert r1 == r2

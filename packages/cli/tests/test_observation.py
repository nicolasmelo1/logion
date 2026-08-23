# SPDX-License-Identifier: MIT
"""Tests for the consolidated observation envelope and consent contract.

The ``ObservationEnvelope`` that used to live in ``cli._observation`` was
merged into ``UsageObservation`` so there is exactly one normative envelope
for a usage record.  These tests cover the fields inherited from the
15.11.1 instrumentation profile: outcome, task_class, duration_bucket,
integration_version, started_at, finished_at.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.usage.observations import (
    DURATION_BUCKETS,
    INTEGRATION_VERSION,
    OUTCOME_VALUES,
    UsageObservation,
    make_observation,
    normalize_observed_at,
    spool_observation,
)


def _observation(**overrides: object) -> UsageObservation:
    defaults: dict[str, object] = {
        "harness": "codex",
        "event": "resource_invoked",
        "resource_id": "res-abc",
        "version_id": "ver-xyz",
        "resource_type": "agent_skill",
        "acquisition_channel": "npx_skills",
        "installation_id": "inst-local-1",
        "scope_kind": "repo-root",
        "scope_id": "scope-opaque-1",
        "session_hash": "sess-opaque-1",
    }
    defaults.update(overrides)
    return make_observation(**defaults)  # type: ignore[arg-type]


class TestConsolidatedEnvelope:
    def test_default_outcome_is_unknown(self) -> None:
        obs = _observation()
        assert obs.outcome == "unknown"

    def test_default_integration_version(self) -> None:
        obs = _observation()
        assert obs.integration_version == INTEGRATION_VERSION

    def test_outcome_accepted(self) -> None:
        for outcome in OUTCOME_VALUES:
            obs = _observation(outcome=outcome)  # type: ignore[arg-type]
            assert obs.outcome == outcome

    def test_invalid_outcome_rejected(self) -> None:
        with pytest.raises(
            ValueError, match="unsupported observation outcome"
        ):
            _observation(outcome="bogus")  # type: ignore[arg-type]

    def test_task_class_accepted(self) -> None:
        obs = _observation(task_class="software-development")
        assert obs.task_class == "software-development"

    def test_task_class_must_be_slug(self) -> None:
        with pytest.raises(ValueError, match="lowercase slug"):
            _observation(task_class="not a slug")

    def test_duration_bucket_accepted(self) -> None:
        for bucket in DURATION_BUCKETS:
            obs = _observation(duration_bucket=bucket)
            assert obs.duration_bucket == bucket

    def test_invalid_duration_bucket_rejected(self) -> None:
        with pytest.raises(ValueError, match="duration_bucket"):
            _observation(duration_bucket="way-too-long")

    def test_started_at_and_finished_at_accepted(self) -> None:
        obs = _observation(
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:05:00Z",
        )
        assert obs.started_at == "2025-01-01T00:00:00Z"
        assert obs.finished_at == "2025-01-01T00:05:00Z"

    def test_finished_before_started_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not precede"):
            _observation(
                started_at="2025-01-01T00:05:00Z",
                finished_at="2025-01-01T00:00:00Z",
            )

    def test_invalid_timestamp_rejected(self) -> None:
        with pytest.raises(ValueError, match="RFC3339"):
            _observation(started_at="not-a-date")

    def test_to_dict_omits_none_optionals(self) -> None:
        obs = _observation()
        d = obs.to_dict()
        assert "task_class" not in d
        assert "duration_bucket" not in d
        assert "started_at" not in d
        assert "finished_at" not in d
        # outcome and integration_version always present (non-None defaults)
        assert d["outcome"] == "unknown"
        assert d["integration_version"] == INTEGRATION_VERSION

    def test_to_jsonl_is_single_line(self) -> None:
        obs = _observation()
        line = obs.to_jsonl()
        assert "\n" not in line
        parsed = json.loads(line)
        assert parsed["integration_version"] == INTEGRATION_VERSION

    def test_is_frozen(self) -> None:
        obs = _observation()
        with pytest.raises(AttributeError):
            obs.outcome = "completed"  # type: ignore[misc]


class TestSpoolWithConsolidatedFields:
    def test_local_only_spools_with_outcome(self, tmp_path: Path) -> None:
        """The spool record carries the new fields."""
        obs = _observation(
            outcome="completed",  # type: ignore[arg-type]
            task_class="software-development",
            duration_bucket="minutes",
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:05:00Z",
        )
        result = spool_observation(obs, logion_home=tmp_path)
        assert result.deduplicated is False
        assert result.record["outcome"] == "completed"
        assert result.record["task_class"] == "software-development"
        assert result.record["duration_bucket"] == "minutes"
        assert result.record["integration_version"] == INTEGRATION_VERSION


class TestNormalizeObservedAt:
    def test_none_stays_none(self) -> None:
        assert normalize_observed_at(None) is None

    def test_isoformat_plus_zero_is_unchanged(self) -> None:
        assert (
            normalize_observed_at("2026-08-23T04:00:00+00:00")
            == "2026-08-23T04:00:00+00:00"
        )

    def test_trailing_z_normalizes_to_plus_zero(self) -> None:
        assert (
            normalize_observed_at("2026-08-23T04:00:00Z")
            == "2026-08-23T04:00:00+00:00"
        )

    def test_zone_offset_is_preserved(self) -> None:
        assert (
            normalize_observed_at("2026-08-23T01:00:00-03:00")
            == "2026-08-23T01:00:00-03:00"
        )

    def test_unparseable_is_left_untouched(self) -> None:
        assert normalize_observed_at("not-a-timestamp") == "not-a-timestamp"

# SPDX-License-Identifier: MIT
"""Tests for the observation envelope and consent contract ."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._observation import (
    AUTO,
    CONSENT_LEVELS,
    INTEGRATION_VERSION,
    LOCAL_ONLY,
    OFF,
    PROMPT,
    ConsentConfig,
    ObservationEnvelope,
    assert_no_secrets,
    observations_dir,
    should_spool,
    spool_envelope,
)


def _envelope() -> ObservationEnvelope:
    return ObservationEnvelope(
        event="resource.use.completed",
        harness="codex",
        harness_session_id="sess-opaque-1",
        installation_id="inst-local-1",
        resource_version_id="rv-abc",
        scope_kind="repo-root",
        scope_id="scope-opaque-1",
        task_class="software-development",
        outcome="completed",
        started_at="2025-01-01T00:00:00Z",
        finished_at="2025-01-01T00:05:00Z",
        integration_version=INTEGRATION_VERSION,
    )


class TestObservationEnvelope:
    def test_construction(self) -> None:
        e = _envelope()
        assert e.event == "resource.use.completed"
        assert e.harness == "codex"
        assert e.outcome == "completed"
        assert e.integration_version == INTEGRATION_VERSION

    def test_to_dict_omits_none(self) -> None:
        e = ObservationEnvelope(
            event="resource.use.completed",
            harness="hermes",
            harness_session_id="s",
            installation_id="i",
            resource_version_id=None,
            scope_kind="user",
            scope_id="sc",
            task_class=None,
            outcome="unknown",
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:00Z",
            integration_version=INTEGRATION_VERSION,
        )
        d = e.to_dict()
        assert "resource_version_id" not in d
        assert "task_class" not in d
        assert d["outcome"] == "unknown"

    def test_to_jsonl_is_single_line(self) -> None:
        e = _envelope()
        line = e.to_jsonl()
        assert "\n" not in line
        parsed = json.loads(line)
        assert parsed["event"] == "resource.use.completed"

    def test_is_frozen(self) -> None:
        e = _envelope()
        with pytest.raises(AttributeError):
            e.event = "other"  # type: ignore[misc]


class TestConsent:
    @pytest.mark.parametrize(
        ("level", "expected"),
        [
            (OFF, False),
            (LOCAL_ONLY, True),
            (PROMPT, True),
            (AUTO, True),
        ],
    )
    def test_should_spool(self, level: str, expected: bool) -> None:
        assert should_spool(level) is expected

    def test_consent_levels_set(self) -> None:
        assert frozenset({OFF, LOCAL_ONLY, PROMPT, AUTO}) == CONSENT_LEVELS

    def test_consent_config_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="unknown consent level"):
            ConsentConfig(level="bogus")

    def test_consent_config_defaults_to_off(self) -> None:
        assert ConsentConfig().level == OFF


class TestNoSecretsInvariant:
    def test_clean_envelope_passes(self) -> None:
        assert_no_secrets(_envelope().to_dict())

    @pytest.mark.parametrize(
        "bad_key",
        [
            "prompt",
            "source_code",
            "tool_arg",
            "secret",
            "token",
            "password",
            "model_context",
            "terminal_output",
            "raw_task_data",
        ],
    )
    def test_forbidden_keys_rejected(self, bad_key: str) -> None:
        payload = _envelope().to_dict()
        payload[bad_key] = "leak"
        with pytest.raises(ValueError, match="forbidden"):
            assert_no_secrets(payload)

    def test_unknown_field_rejected(self) -> None:
        payload = _envelope().to_dict()
        payload["random_extra"] = "x"
        with pytest.raises(ValueError, match="not permitted"):
            assert_no_secrets(payload)

    def test_invalid_structured_values_are_rejected(self) -> None:
        payload = _envelope().to_dict()
        payload["task_class"] = "raw prompt with spaces"
        with pytest.raises(ValueError, match="lowercase slug"):
            ObservationEnvelope(**payload)

        payload = _envelope().to_dict()
        payload["scope_id"] = "/Users/nico/private/repo"
        with pytest.raises(ValueError, match="opaque identifier"):
            ObservationEnvelope(**payload)

        payload = _envelope().to_dict()
        payload["finished_at"] = "2024-01-01T09:59:00Z"
        with pytest.raises(ValueError, match="must not precede"):
            ObservationEnvelope(**payload)


class TestSpool:
    def test_off_does_not_spool(self, tmp_path: Path) -> None:
        path = spool_envelope(_envelope(), consent=OFF, logion_home=tmp_path)
        assert path is None
        assert not (tmp_path / "observations").exists()

    def test_local_only_spools_jsonl(self, tmp_path: Path) -> None:
        path = spool_envelope(
            _envelope(), consent=LOCAL_ONLY, logion_home=tmp_path
        )
        assert path is not None
        assert path == tmp_path / "observations" / "observations.jsonl"
        line = path.read_text().strip()
        parsed = json.loads(line)
        assert parsed["event"] == "resource.use.completed"
        assert "prompt" not in parsed
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700

    def test_unknown_consent_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="unknown consent level"):
            spool_envelope(
                _envelope(), consent="invalid", logion_home=tmp_path
            )

    def test_observations_dir_respects_logion_home(
        self, tmp_path: Path
    ) -> None:
        assert observations_dir(tmp_path) == tmp_path / "observations"

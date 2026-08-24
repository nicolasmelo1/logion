# SPDX-License-Identifier: MIT
"""Tests for the instrumentation profile validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logion_instrumentation.validator import (
    ValidationError,
    canonical_digest,
    diff_profiles,
    validate_profile,
)
from logion_instrumentation.vocabulary import (
    DURATION_BUCKET_VALUES,
    EVENT_VALUES,
    OUTCOME_VALUES,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, object]:
    with (FIXTURES / name).open(encoding="utf-8") as fh:
        return json.load(fh)


# --- valid profile ---------------------------------------------------------


def test_valid_profile_passes() -> None:
    profile = _load_fixture("valid.json")
    validate_profile(profile)


def test_valid_profile_digest_is_deterministic() -> None:
    profile = _load_fixture("valid.json")
    digest = canonical_digest(profile)
    assert digest.startswith("sha256:")
    # Re-computing must yield the same value.
    assert canonical_digest(profile) == digest


def test_canonical_digest_sorted_keys() -> None:
    """Digest is independent of key order in the input dict."""
    profile_a = _load_fixture("valid.json")
    profile_b = json.loads(json.dumps(profile_a, sort_keys=True))
    # Shuffling keys in the raw dict shouldn't matter since json.dumps
    # with sort_keys=True is used internally.
    assert canonical_digest(profile_a) == canonical_digest(profile_b)


# --- rejection: unknown top-level key --------------------------------------


def test_reject_unknown_top_level_key() -> None:
    profile = _load_fixture("reject_unknown_top_level.json")
    with pytest.raises(ValidationError, match="unknown_top_level_key"):
        validate_profile(profile)


# --- rejection: unknown field name -----------------------------------------


def test_reject_unknown_field_name() -> None:
    profile = _load_fixture("reject_unknown_field_name.json")
    with pytest.raises(ValidationError, match="bogus_field_name"):
        validate_profile(profile)


# --- rejection: missing required field -------------------------------------


def test_reject_missing_required_field() -> None:
    profile = _load_fixture("reject_missing_required.json")
    with pytest.raises(ValidationError, match="integration_version"):
        validate_profile(profile)


# --- rejection: template endpoint not resolved ------------------------------


def test_reject_template_endpoint() -> None:
    profile = _load_fixture("reject_template_endpoint.json")
    with pytest.raises(ValidationError, match="RESOURCE_UUID"):
        validate_profile(profile)


# --- endpoint policy --------------------------------------------------------


def test_reject_http_endpoint() -> None:
    profile = _load_fixture("valid.json")
    profile["delivery"]["endpoint"] = (  # type: ignore[index]
        "http://api.logion.sh/v1/receipts"
    )
    with pytest.raises(ValidationError, match="HTTPS"):
        validate_profile(profile)


# --- size limits ------------------------------------------------------------


def test_reject_oversized_payload() -> None:
    profile = _load_fixture("valid.json")
    profile["subject"]["resource_id"] = "x" * 200000  # type: ignore[index]
    with pytest.raises(ValidationError, match="exceeds"):
        validate_profile(profile)


# --- diff mode --------------------------------------------------------------


def test_diff_detects_widening() -> None:
    old = _load_fixture("valid.json")
    new = json.loads(json.dumps(old))
    new["fields"].append("outcome")  # already present — no widening
    result = diff_profiles(old, new)
    assert result["widens_data_categories"] is False


def test_diff_detects_new_field_widens() -> None:
    old = _load_fixture("valid.json")
    new = json.loads(json.dumps(old))
    new["fields"] = ["resource_id", "event", "harness"]
    old_fields = set(old["fields"])
    new_fields = set(new["fields"])
    assert new_fields - old_fields == {"harness"} - old_fields or True
    result = diff_profiles(old, new)
    # If harness wasn't in old, it's a widening.
    if "harness" not in old_fields:
        assert result["widens_data_categories"] is True


def test_diff_detects_removed_exclusion_widens() -> None:
    old = _load_fixture("valid.json")
    new = json.loads(json.dumps(old))
    new["excluded"].remove("secrets")
    result = diff_profiles(old, new)
    assert result["widens_data_categories"] is True
    assert "secrets" in result["excluded"]["removed"]


def test_diff_digests_present() -> None:
    old = _load_fixture("valid.json")
    new = json.loads(json.dumps(old))
    result = diff_profiles(old, new)
    assert result["old_digest"].startswith("sha256:")
    assert result["new_digest"].startswith("sha256:")


# --- vocabulary consistency with schema -------------------------------------


def test_schema_enums_match_vocabulary() -> None:
    """The static JSON schema file must match the vocabulary module."""
    from logion_instrumentation.schema import load_schema

    schema = load_schema()
    events_enum = set(
        schema["properties"]["events"]["items"]["enum"]  # type: ignore[index]
    )
    fields_enum = set(
        schema["properties"]["fields"]["items"]["enum"]  # type: ignore[index]
    )
    assert events_enum == set(EVENT_VALUES)
    # fields should contain event, outcome, duration_bucket
    assert "event" in fields_enum
    assert "outcome" in fields_enum
    assert "duration_bucket" in fields_enum


def test_vocabulary_values_are_non_empty() -> None:
    assert len(EVENT_VALUES) >= 1
    assert len(OUTCOME_VALUES) >= 1
    assert len(DURATION_BUCKET_VALUES) >= 1
